---
title: "ADR 0038: Dual-Plane Telemetry API Taxonomy, State Heartbeat, and Source Transparency"
status: "proposed"
date: "2026-11-08"
deciders: ["Core Architecture Team"]
consults: ["ADR 0022", "ADR 0023", "ADR 0036", "ADR 0037"]
informs: ["All Engineers"]
tags: ["adr", "api", "telemetry", "state-plane", "heartbeat", "rest", "taxonomy"]
---

# ADR 0038: Dual-Plane Telemetry API Taxonomy, State Heartbeat, and Source Transparency

## Context and Problem Statement

During integration testing of downstream client applications (e.g. `ed-integration-smoke`, copilot overlays, and annunciators), several critical friction points and ambiguities emerged regarding the driving HTTP interface:

1. **Unreliable "New" Content Detection in Head State:**
   `GET /api/v1/telemetry/head` (ADR 0036, ADR 0037) returns a point-in-time snapshot. However, clients polling `/telemetry/head` cannot distinguish whether the data has changed since the last request without computing expensive deep comparisons across JSON trees. When clients poll fast, they waste compute diffing static data; when they poll slowly, they experience noticeable latency.
2. **Confusing & Counterintuitive Endpoint Paths:**
   The current path structure lacks semantic consistency:
   * `/api/v1/status` (watcher service state) vs. `/api/v1/status/game` (in-game cockpit telemetry).
   * `/api/v1/events` is overly vague: it queries persistent historical SQLite records, whereas `/api/v1/events/buffer` destructively drains an in-memory queue.
   * `/api/v1/stream` sits at the root namespace rather than alongside event subscriptions.
   * `/api/v1/control/watch` uses an RPC-style action verb in the URL path.
3. **Data Source Ambiguity (In-Memory Buffer vs. SQLite DB):**
   Callers cannot determine which endpoints hit transient in-memory ring buffers versus durable SQLite WAL storage, leading to misconceptions regarding persistence guarantees, query latency, and side effects (e.g. destructive queue draining vs. read-only queries).
4. **Cold-Start Replay vs. Model State Hydration:**
   Callers maintaining domain models need all current state populated immediately upon connection without racing through thousands of historical journal entries. Yet they need to be confident that `ed-telemetry`'s pure boundary (an agnostic telemetry pipeline, not a game-state business engine) is strictly preserved.

How should `ed-telemetry` organize its HTTP API taxonomy to provide intuitive paths, explicit data source transparency, instant state hydration, and low-latency change detection while adhering to hexagonal boundaries?

---

## Decision Drivers

* **Explicit Dual-Plane Architecture:** Strict separation between the **State Plane** (instantaneous, non-destructive game state hydration) and the **Log Plane** (time-series historical queries and streaming feeds).
* **Zero-Replay Cold-Start Hydration:** Callers must be able to hydrate all local models in a single call without scanning historical logs.
* **Lightweight Delta & Change Detection:** Support high-frequency polling (< 100ms) with minimal overhead (< 200 bytes) via a dedicated heartbeat and standard HTTP cache controls (`ETag`).
* **Source Transparency:** Every response must explicitly inform the caller of the underlying storage tier (`in-memory`, `sqlite-wal`, or `hybrid`).
* **Non-Breaking Path Evolution:** Maintain legacy `/api/v1/*` paths as aliases with deprecation notices to avoid breaking existing integrations.
* **Hexagonal Architectural Purity:** `ed-telemetry` must remain an agnostic ingestion and distribution engine; it must not interpret game mechanics, derive complex ship states, or violate boundary invariants.

---

## Considered Options

* **Option 1: Complete v2 Breaking Rewrite (`/api/v2/*`).** Deprecate all v1 endpoints and force callers to migrate immediately.
  * *Drawbacks:* High friction for existing fleet integrations; breaks existing test suites and tools.
* **Option 2: Status Quo with Better Documentation.** Keep all endpoints as-is and document data sources in markdown.
  * *Drawbacks:* Fails to resolve the underlying developer experience issues, ambiguous paths, or uncoordinated client polling overhead.
* **Option 3: Dual-Plane Taxonomy, Heartbeat Endpoint, and Source Headers (Selected).**
  Introduce structured `/api/v1/state/*`, `/api/v1/journal/*`, and `/api/v1/system/*` paths with legacy aliases, add a lightweight `/api/v1/state/heartbeat` endpoint, inject `X-Telemetry-Source` response headers, and support `ETag` on state endpoints.

---

## Decision Outcome

Chosen Option: **Option 3: Dual-Plane Taxonomy, Heartbeat Endpoint, and Source Headers**.

### 1. Dual-Plane Model Architecture

The HTTP interface is partitioned into two functional planes and an operational control group:

1. **State Plane (`/api/v1/state/*`):**
   * **Purpose:** Represents instantaneous gameplay state. Non-destructive, idempotent, and backed by memory-cached files.
   * **Primary Target:** Model initialization, dashboard gauges, current system/ship status.
2. **Journal Plane (`/api/v1/journal/*`):**
   * **Purpose:** Represents append-only historical event logs and streams.
   * **Primary Target:** Event processing loops, audit logging, mission/trade history replay.
3. **System Plane (`/api/v1/system/*`):**
   * **Purpose:** Daemon operations, ingestion watcher health, diagnostic log inspection, and reactor control.

---

### 2. Comprehensive Endpoint Transition Mapping

| Proposed Canonical Endpoint | HTTP Method | Data Source | Sourcefile Contents | Legacy Route (Deprecated Alias) | Status | Description & Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/v1/state/heartbeat` | `GET` | In-memory | `all` | *None* | **New** | Returns lightweight monotonic sequence ID, event ID, hashes, and timestamp (< 200B) for fast delta detection. |
| `/api/v1/state/head` | `GET` | Memory + SQLite | `all` | `/api/v1/telemetry/head` | **Migrated** | Full instantaneous hydration: active journal, latest journal event, `Status.json`, and all auxiliary snapshots. Supports `ETag`. |
| `/api/v1/state/game` | `GET` | In-memory | `status` | `/api/v1/status/game` | **Migrated** | Returns current raw payload and hash of `Status.json`. |
| `/api/v1/state/snapshots/{name}` | `GET` | In-memory | `snapshot` | `/api/v1/snapshots/{name}` | **Migrated** | Returns raw payload and hash of specified auxiliary snapshot (e.g. `Market`, `Cargo`). |
| `/api/v1/journal/records` | `GET` | SQLite DB | `journal` | `/api/v1/events` | **Migrated** | Queries historical records in SQLite WAL. Supports `since_id`, `topic`, `limit`, and `order`. |
| `/api/v1/journal/queue` | `GET` | In-memory buffer | `journal` | `/api/v1/events/buffer` | **Migrated** | Destructively drains and returns queued events from the in-memory ring buffer. |
| `/api/v1/journal/stream` | `GET` | Stream generator | `all` | `/api/v1/stream` | **Migrated** | Continuous live Server-Sent Events (SSE) feed. |
| `/api/v1/system/health` | `GET` | In-memory | N/A | `/api/v1/health` | **Migrated** | Daemon liveness probe (`{"status":"ok"}`). |
| `/api/v1/system/watcher` | `GET` | In-memory | `journal` | `/api/v1/status` | **Migrated** | Telemetry watcher operational status and monitored directory path. |
| `/api/v1/system/logs` | `GET` | In-memory buffer | N/A | `/api/v1/diagnostics/logs` | **Migrated** | Retrieves in-memory diagnostic application logs (`min_level`, `limit`). |
| `/api/v1/system/control` | `POST` | Reactor loop | N/A | `/api/v1/control/watch` | **Migrated** | Controls ingestion thread lifecycle (`{"action":"start"|"stop"}`). |

---

### 3. Change Detection & State Heartbeat Specification

To resolve unreliable "new" content detection on `/telemetry/head` without requiring callers to replay logs:

* **Endpoint:** `GET /api/v1/state/heartbeat`
* **Response Contract (`TelemetryHeartbeatDTO`):**
  ```json
  {
    "state_sequence": 1042,
    "timestamp": "2026-11-08T15:00:00.123456+00:00",
    "active_journal": "Journal.2026-11-08T100000.01.log",
    "latest_event_id": "c1f7b098-a3f4-41d7-b8d4-8d48e8a6042a",
    "status_hash": "365d6ebac12925c3",
    "snapshot_hashes": {
      "Market": "065b4bcd26175059",
      "Cargo": "e3b0c44298fc1c14"
    }
  }
  ```
* **Client Polling Pattern:**
  1. Call `GET /api/v1/state/head` once at startup to hydrate all local models.
  2. Poll `GET /api/v1/state/heartbeat` every 200–500ms.
  3. If `state_sequence` matches the local sequence, abort processing (no changes).
  4. If `status_hash` changed, fetch `/api/v1/state/game`.
  5. If `snapshot_hashes[name]` changed, fetch `/api/v1/state/snapshots/{name}`.
  6. If `latest_event_id` changed, fetch new journal rows via `/api/v1/journal/records?since_id=...` or `/api/v1/state/head`.

---

### 4. Storage Source Transparency Headers

To eliminate ambiguity between memory buffers and durable disk storage, the HTTP server adapter injects an explicit diagnostic header on every response:

* `X-Telemetry-Source: memory-buffer` — Request served strictly from in-memory ring buffers or RAM caches.
* `X-Telemetry-Source: sqlite-wal` — Request served via SQLite queries from disk.
* `X-Telemetry-Source: hybrid` — Request aggregated across memory caches and SQLite.
* `X-Telemetry-Plane: state | journal | system` — Categorizes the architectural plane of the invoked endpoint.

---

## Consequences

### Positive
* **Intuitive Developer Experience:** Endpoint paths reflect their architectural role (`/state/*`, `/journal/*`, `/system/*`).
* **Ultra-Low Bandwidth Change Polling:** Clients track state deltas via sub-millisecond heartbeats without JSON tree diffing.
* **Elimination of Data Ambiguity:** `X-Telemetry-Source` and explicit naming distinguish destructive queue reads from durable queries.
* **Preservation of Hexagonal Scope:** `ed-telemetry` remains purely an event distribution and snapshot aggregation engine; no game logic or model interpreting is introduced.
* **Backward Compatibility:** All existing v1 endpoints remain active as legacy aliases.

### Negative / Trade-offs
* **Larger Routing Table:** `HttpApiAdapter` must route both canonical and deprecated endpoints.
* **Sequence Tracking Overhead:** Core ingestion must maintain an atomic monotonic state sequence integer incremented on journal or snapshot updates.
