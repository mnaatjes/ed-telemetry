---
title: "ADR 0025: Diagnostics Logging, Error Bubbling, and API Transport Architecture"
tags: ["adr", "logging", "diagnostics", "api", "streaming", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0025: Diagnostics Logging, Error Bubbling, and API Transport Architecture

## Status
Accepted

## Context
In ADR 0020, `ed-telemetry` prohibited outbound HTTP client dependencies (`requests`, `httpx`, `aiohttp`) to ensure the package remains lean, local, and protected from feature creep.

Operators and downstream ecosystem tools (such as `ed-broadcast`) require visibility into internal operations, warnings, and errors to:
1. Stream log and audit events live during execution.
2. Inspect recent errors and warnings on demand without accessing raw host filesystems.
3. Diagnose issues on remote target hosts (e.g., Windows gaming rigs) without breaking zero-dependency, local-only boundaries.

### Codebase Review & Current State
1. **Watcher Audit System:** The watcher engine (`WatcherReactor`, `tailer`, `snapshot_reader`) already generates rich, typed control-plane events (`WatcherAuditEvent` / `WatcherAuditEventDTO`) representing lifecycle states (`part_rollover`, `line_quarantined`, `retry_backoff`, `poll_tick`, `casing_collision_detected`).
2. **Disconnected Audit Sink:** `FileSystemWatcher._dispatch_audit()` currently only invokes registered callbacks, but `ProcessTelemetryStreamUseCase` only registers a handler for data events (`FileIngestionEventDTO`). Audit events and errors are not forwarded to egress sinks.
3. **Logging Configuration:** Standard Python `logging.getLogger(__name__)` is invoked in `watcher.py` but has no configured rotating file or ring buffer handler; unhandled errors print to stderr via `logging.lastResort` and are lost in headless mode.

## Decision

We adopt a dual-channel architecture using the local HTTP driving API for all log and error transport:

### 1. Option A: Real-Time Streaming & Persistence (`telemetry.audit`)
- **Error Bubbling:** `ProcessTelemetryStreamUseCase` registers an audit handler with `WatcherPort.register_audit_handler()`.
- **Egress Normalization:** Audit events are converted into standard `TelemetryPayloadDTO` with topic `telemetry.audit`.
- **Fan-out:** Like game telemetry, audit events fan out through `CompositeEgressAdapter` to:
  1. The in-memory buffer (`BufferedQueueAdapter`), making them immediately available in `/api/v1/stream` (SSE) and `/api/v1/events/buffer`.
  2. The SQLite database (`SqliteEgressAdapter`), enabling indexed historical querying via `GET /api/v1/events?topic=telemetry.audit`.

### 2. Option B: Point-in-Time Diagnostic Snapshot (`/api/v1/diagnostics/logs`)
- **Ring Buffer Logging Handler:** A zero-dependency memory-bounded `DiagnosticLogBuffer` (subclassing standard `logging.Handler`) retains the last $N$ application log records (default 200).
- **Driving Port & Use Case:**
  - Driven Port: `DiagnosticLogPort` in `core/ports/driven/`.
  - Driving Port: `GetDiagnosticLogsPort` in `core/ports/driving/`.
  - Use Case: `GetDiagnosticLogsUseCase` in `core/use_cases/`.
- **Endpoint:** `GET /api/v1/diagnostics/logs` returns recent log records filtered optionally by minimum level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

### 3. Hexagonal Boundaries & Compliance
- **Core Isolation:** Core layers do not depend on `logging.Handler` or `http.server`. They interact strictly via DTOs (`DiagnosticLogRecordDTO`, `DiagnosticLogSnapshotDTO`).
- **Headless Local Storage:** `bootstrap/container.py` configures standard library `logging.handlers.RotatingFileHandler` writing to `.cache/ed-telemetry.log` alongside `telemetry.db`.
- **Zero Outbound Exception:** No exceptions to ADR 0020 are granted. `ed-telemetry` remains strictly passive; downstream tools like `ed-broadcast` pull from or subscribe to the API.

## Consequences
- Complete, real-time observability over SSE and queryable history via SQLite without new external dependencies.
- Snapshot diagnostic inspections available via a dedicated endpoint for fast troubleshooting.
- 100% compliance with hexagonal boundaries and ADR 0020 guardrails.
