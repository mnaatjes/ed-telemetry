---
title: "ADR 0037: Active Journal Tail State Resolution in Consolidated Head Endpoint"
status: "accepted"
date: "2026-11-08"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0008", "ADR 0022", "ADR 0023", "ADR 0036"]
informed: ["All Engineers"]
tags: ["adr", "api", "telemetry", "head-state", "journal", "concurrency"]
---

# ADR 0037: Active Journal Tail State Resolution in Consolidated Head Endpoint

## Context and Problem Statement

ADR 0036 introduced `/api/v1/telemetry/head` as the non-destructive state inspection endpoint for downstream copilots, resolving instantaneous cockpit state (`Status.json`), auxiliary snapshots (`Market.json`, `Shipyard.json`), and the latest journal event.

Under ADR 0036, the `latest_journal_event` field was implemented by querying the SQLite persistent store:
```python
latest_records = self._repository.find_events(TelemetryQueryDTO(topic="telemetry.journal", limit=1, order="desc"))
```
This queries `SELECT * FROM telemetry_events WHERE topic = 'telemetry.journal' ORDER BY id DESC LIMIT 1`.

When `ed-telemetry` runs against an installation with historical journal archives (e.g. dozens of prior sessions), the background filesystem scanner ingests historical files into the database. Because older journal files are actively inserted with newer auto-incrementing SQLite `id`s, `ORDER BY id DESC` resolves whatever historical record SQLite happened to insert most recently, rather than the active session's latest event.

Furthermore, `ORDER BY id DESC` creates structural coupling between immediate head-state inspection and database ingestion throughput. While `game_status` and auxiliary `snapshots` read disk files directly with zero latency, `latest_journal_event` experiences backfill distortion.

How should `ed-telemetry` resolve the `latest_journal_event` in `TelemetryHeadDTO` to guarantee real-time immediacy and complete immunity to historical database ingestion?

## Decision Drivers

* **Real-Time Immediacy:** The consolidated head state must reflect current active gameplay (sub-millisecond latency), matching the behavior of `Status.json` and snapshot files.
* **Immunity to Database Backfill:** Ingesting historical archives must never corrupt or displace the active session's current event in the head endpoint.
* **Constant Time ($O(1)$) Resolution:** Resolving the latest event must not scan large database tables or traverse entire journal log files.
* **Fault Tolerance & Graceful Fallback:** If the active journal is missing, empty, or momentarily inaccessible, the system must fall back transparently to the database index without raising unhandled exceptions.
* **Hexagonal Boundary Purity:** Filesystem access must remain strictly isolated within driven watcher adapters, exposed through driven port contracts (`WatcherPort`), and orchestrated by the application use case (`GetTelemetryHeadUseCase`).

## Considered Options

* **Option 1: Query Database with `ORDER BY timestamp DESC`.** Add an index on `(topic, timestamp DESC)` and sort by the event's in-game timestamp.
  * *Drawbacks:* Requires indexing hundreds of thousands of rows; introduces sorting overhead; if SQLite write locks or ingestion buffers delay insertion of the latest active line, the query remains behind real time.
* **Option 2: Active Journal Tail Read via Watcher Port (Selected).** Delegate active journal tail inspection to `WatcherPort`. The watcher resolves the currently active journal path via `JournalSelector`, executes a constant-time $O(1)$ reverse seek to the last line, parses the JSON payload into `TelemetryRecordDTO`, and returns it directly to `GetTelemetryHeadUseCase` with database fallback.

## Decision Outcome

Chosen Option: **Option 2: Active Journal Tail Read via Watcher Port**.

### Architectural Invariants & Mechanics

1. **Port Contract Extension (`WatcherPort`):**
   * Add `read_active_journal_tail() -> TelemetryRecordDTO | None` to `WatcherPort` in `ed_telemetry.core.ports.driven.telemetry_driven_port`.
2. **$O(1)$ Reverse Seek Implementation (`Watcher`):**
   * The watcher retrieves the active journal candidate via `JournalSelector.get_active_journal()`.
   * Opens the active journal in binary mode, seeks backwards from EOF to locate the trailing newline, and reads the final line into memory without reading previous lines.
   * Parses the line into a JSON payload, computes the SHA-256 hash, extracts the event timestamp, and constructs a `TelemetryRecordDTO` (with `id=None` to denote unpersisted real-time state).
3. **Use Case Orchestration (`GetTelemetryHeadUseCase`):**
   * `GetTelemetryHeadUseCase.get_head()` invokes `self._watcher_port.read_active_journal_tail()`.
   * If an active journal record is returned, it is assigned to `head.latest_journal_event`.
   * If `None` is returned (e.g. no active journal discovered), it falls back to querying the repository database: `self._repository.find_events(TelemetryQueryDTO(topic="telemetry.journal", limit=1, order="desc"))`.

### Consequences

* **Positive:**
  * Zero-latency head state: `telemetry/head` immediately reflects dockings, jumps, and scans regardless of whether SQLite is ingesting millions of historical rows.
  * Consistent architectural model: `latest_journal_event` follows the exact same disk-level snapshot pattern as `game_status` and `snapshots`.
  * $O(1)$ constant-time execution with negligible CPU and memory overhead.
* **Negative:**
  * The `TelemetryRecordDTO` returned by tail seek has `id=None` because it reflects uncommitted live state prior to database persistence. Downstream clients consuming `/telemetry/head` must treat `id` as nullable on head inspection.
