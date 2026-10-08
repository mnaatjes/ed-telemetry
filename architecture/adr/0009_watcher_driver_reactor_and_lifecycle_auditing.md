---
title: "ADR 0009: Watcher Driver Reactor, Lifecycle Auditing, and Fault Recovery"
status: "proposed"
date: "2026-10-08"
tags: ["architecture", "adr", "watcher", "reactor", "driver", "auditing", "madr"]
---

# ADR 0009: Watcher Driver Reactor, Lifecycle Auditing, and Fault Recovery

## 1. Context and Problem Statement

The `ed_watcher` subsystem requires an execution driver to coordinate candidate selection ([ADR 0006](0006_active_journal_candidate_selection_and_sorting.md), [ADR 0007](0007_status_and_snapshot_file_identification.md)) and physical I/O ingestion ([ADR 0008](0008_file_ingestion_io_freshness_and_concurrency.md)).

Determining *when* to check files across heterogeneous platforms presents operational challenges:
- **Kernel Event Differences**: Windows `ReadDirectoryChangesW` and Linux `inotify` emit filesystem events efficiently on local drives.
- **Proton / Wine & Network Mount Drops**: When Elite Dangerous runs inside Proton/Wine or directories reside on container bind-mounts or network shares, kernel notification events frequently fail to propagate to external processes.
- **Fault Recovery**: Unreadable files, corrupt byte sequences, or drive unmounts must not crash the long-running application process.

We require an architectural decision for the watcher event loop, operational diagnostics/auditing, and fault isolation.

---

## 2. Decision Drivers

* **Continuous Liveness Guarantee:** Telemetry must never stall indefinitely due to dropped kernel filesystem events.
* **Low CPU / I/O Footprint:** When idle, the system must not spin CPU in tight polling loops.
* **Decoupled Observability:** Operational transitions (discovery, selection, retries, quarantine) must be auditable without polluting domain models.
* **Supervised Fault Tolerance:** Corrupt lines or transient I/O exceptions must be caught, recorded, and recovered from gracefully.

---

## 3. Considered Options

* **Option 1: Pure Polling Loop (Ticker Only)**
  - Simple and reliable across Wine/Proton, but introduces static latency (e.g. 1s lag) and continuous disk I/O chatter even when the game is idle.
* **Option 2: Pure Filesystem Event Watcher (`watchdog` / `inotify` Only)**
  - Sub-millisecond latency on local desktops, but vulnerable to silent deadlocks if Wine or container mounts drop kernel notification events.
* **Option 3: Hybrid Reactive Reactor with Supervised Audit Lifecycle (Recommended)**
  - **Hybrid Event Driver**: Blocks on an async event signal triggered immediately by OS filesystem notifications (`on_created`, `on_modified`), with a bounded fallback timeout tick (1.0s on Windows, 0.5s on Wine/Linux).
  - **Audit Logging**: Emits `WatcherAuditEvent` records categorized via `WatcherAuditAction` enum (`DISCOVERED`, `SELECTED`, `POLL_TICK`, `FRESHNESS_VERIFIED`, `RETRY_BACKOFF`, `PART_ROLLOVER`, `LINE_QUARANTINED`).
  - **Circuit Breaker / Line Quarantine**: Unparseable byte sequences are logged to an audit event and skipped to the next newline (`\n`), allowing ingestion to continue uninterrupted.

---

## 4. Decision Outcome

Chosen Option: **Option 3: Hybrid Reactive Reactor with Supervised Audit Lifecycle.**

### Architectural Specification

1. **Hybrid Reactor Loop**:
   - Primary driver: `watchdog` registering listeners for `on_created` (rollover detection) and `on_modified` (append notification).
   - Liveness heartbeat: Async wait with bounded timeout (`timeout=1.0` on Windows, `timeout=0.5` on Linux/Wine).
   - If OS event fires, wake immediately; if timeout expires, execute fallback freshness check.
2. **Lifecycle Audit Records**:
   ```python
   @dataclass(frozen=True)
   class WatcherAuditEvent:
       timestamp: datetime
       action: WatcherAuditAction
       target_path: Path
       detail: str = ""
   ```
3. **Rollover Transition**:
   - When active journal reads EOF, query candidate selector for successor (`part + 1`).
   - If successor exists, drain remaining bytes of current file, close descriptor, emit `WatcherAuditEvent(PART_ROLLOVER)`, and bind handle to successor.

---

## 5. Consequences

### Positive
* **100% Liveness Guarantee**: The 0.5s/1.0s timeout ticker guarantees ingestion never freezes even if Wine or host mount layers drop inotify events.
* **Sub-Millisecond Native Reactivity**: On native Windows and Linux desktops, kernel events dispatch instantly without waiting for poll intervals.
* **Robust Observability**: Diagnostics, health metrics, and quarantine alerts are emitted through structured `WatcherAuditEvent` instances.

### Negative
* Adds `watchdog` as a project dependency to handle cross-platform filesystem event drivers.
