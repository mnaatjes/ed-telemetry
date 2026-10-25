---
title: "ADR 0027: CLI Hybrid IPC Architecture and Canonical State Path Anchoring"
tags: ["adr", "cli", "ipc", "persistence", "sqlite", "xdg", "logging", "process-isolation"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0027: CLI Hybrid IPC Architecture and Canonical State Path Anchoring

## 1. Context and Problem Statement

Following host testing of `ed-telemetry v0.4.0` against an active session of *Elite Dangerous: Odyssey*, four critical bugs were uncovered stemming from operating system process isolation and unanchored relative paths:

1. **Issue #69 (Unanchored Relative DB Path):** The SQLite database path defaulted to `Path(".cache/telemetry.db")` in `container.py`. When an operator runs CLI commands from different directories (e.g. `/tmp`, `~/src`, `~`), SQLite files are created in the current working directory, polluting project trees and fragmenting historical telemetry data.
2. **Issue #68 (Null Status Reporting):** `ed-telemetry status` returns `monitored_directory: null` and `active_journal: null`. The `FileSystemWatcher.journal_dir` property fails to invoke lazy discovery (unlike `read_status_snapshot()`), and `GetWatcherStatusUseCase` hardcodes `active_journal=None`.
3. **Issue #70 (Diagnostic Log Disconnect):** `ed-telemetry logs` always returns `Diagnostic Logs (0 records):` because it inspects an in-memory ring buffer instantiated inside the ephemeral CLI process rather than querying the running daemon or reading the on-disk rotating log file.
4. **Issue #67 (Empty Telemetry Tail):** `ed-telemetry tail` hangs indefinitely without printing events because it neither starts a local watcher lifecycle nor connects to the running daemon's Server-Sent Events (SSE) stream (`/api/v1/stream`).

## 2. Decision Drivers

* **Process Boundary Decoupling:** Operators must be able to inspect status, query logs, and tail telemetry whether `ed-telemetry serve` is running in the background or not.
* **Zero Runtime Dependencies (ADR 0020, ADR 0024):** Inter-process queries and SSE streaming must use Python's standard library (`urllib.request`, `http.client`) without third-party frameworks.
* **Filesystem & State Standards:** Durable telemetry persistence must adhere to canonical OS state locations (`$XDG_DATA_HOME` on Linux, `%LOCALAPPDATA%` on Windows) rather than relative paths in `$CWD`.
* **Hexagonal Architectural Integrity:** Driving adapters must interact strictly through use cases or transport boundaries without leaking infrastructure details into the domain.

## 3. Considered Options

* **Option 1 (Daemon-Only Requirement):** Require that all CLI inspection commands (`status`, `logs`, `tail`) strictly fail unless `ed-telemetry serve` is actively running.
  * *Drawbacks:* Breaks standalone offline inspection, ad-hoc status checking, and scripting workflows.
* **Option 2 (Standalone-Only Execution):** Have each CLI command always start an isolated local watcher and query local files without IPC.
  * *Drawbacks:* Fails when a daemon is already running (locking files or conflicting on port), cannot retrieve daemon-buffered diagnostic logs or active streaming state.
* **Option 3 (Hybrid IPC with Standalone Fallback):**
  * Anchor default SQLite storage to canonical OS data paths (`resolve_default_db_path()`).
  * In the CLI adapter, attempt a lightweight HTTP query to the local daemon (`http://127.0.0.1:8080/api/v1/`):
    * If the daemon responds: proxy `status`, `logs`, and `tail` (SSE stream) through the active daemon.
    * If the daemon is unreachable: seamlessly fall back to local disk/watcher inspection (reading the on-disk rotating log file, initiating local standalone watcher tailing, and running lazy path discovery).

## 4. Decision Outcome

Chosen Option: **Option 3 (Hybrid IPC with Standalone Fallback)**.

### Architectural Invariants

* **Invariant 1 (Canonical State Anchoring):** Default SQLite persistence is anchored via `resolve_default_db_path()` to `%LOCALAPPDATA%\ed-telemetry\telemetry.db` on Windows and `${XDG_DATA_HOME:-~/.local/share}/ed-telemetry/telemetry.db` on Linux. Relative `.cache/` directory creation in `$CWD` is forbidden.
* **Invariant 2 (Lazy Path Discovery on Status Inspection):** `FileSystemWatcher.journal_dir` must trigger automated path discovery when uninitialized, ensuring `monitored_directory` is populated on the first inspection.
* **Invariant 3 (Active Journal Succession):** `GetWatcherStatusUseCase` must query the active candidate from `JournalSelector` or `WatcherPort.list_journals()` rather than returning `None`.
* **Invariant 4 (Zero-Dependency Daemon IPC):** The CLI adapter implements a lightweight standard-library client to probe `http://127.0.0.1:8080/api/v1/health`. If healthy:
  * `ed-telemetry status` proxies to `GET /api/v1/status` (reporting true daemon `is_active: true`).
  * `ed-telemetry logs` proxies to `GET /api/v1/diagnostics/logs`.
  * `ed-telemetry tail` consumes `GET /api/v1/stream` (SSE).
* **Invariant 5 (Standalone Fallback):** If the daemon probe fails (connection refused or timeout):
  * `ed-telemetry status` evaluates local filesystem path discovery.
  * `ed-telemetry logs` parses recent entries from `resolve_default_log_path()` on disk.
  * `ed-telemetry tail` activates a local standalone `ProcessTelemetryStreamUseCase` lifecycle (`start_streaming() ... stop_streaming()`).
* **Invariant 6 (Daemon Startup Banner & POSIX Conventions):** In compliance with 12-Factor App and POSIX daemon conventions, `ed-telemetry serve` must print an informative startup banner detailing bound network interfaces, resolved journal directory, discovery strategy source, active journal file, and endpoint URLs:
  ```text
  Starting ed-telemetry daemon on 127.0.0.1:8080...
  Discovered Journal Directory: /path/to/Saved Games/.../Elite Dangerous (Source: LinuxProtonStrategy)
  Active Journal: Journal.2026-10-25T142610.01.log
  HTTP/SSE API listening on http://127.0.0.1:8080/api/v1
  Press Ctrl+C to stop.
  ```
* **Invariant 7 (Fast-Fail Discovery Failure & Actionable Remediation):** If automated discovery cannot resolve a valid journal directory during `serve`, the daemon must not silently idle. It must immediately fast-fail with POSIX exit code `1` and actionable operator remediation commands pointing to `--journal-dir` and `$ED_JOURNAL_DIR`:
  ```text
  [ERROR] Failed to discover Elite Dangerous journal directory.
  Evaluated strategies: Windows Registry, Steam Proton (AppID 359320), Default User Paths.
  Remediation:
    1. Pass the path explicitly: ed-telemetry serve --journal-dir "/path/to/journal/folder"
    2. Or set environment variable: export ED_JOURNAL_DIR="/path/to/journal/folder"
  ```
* **Invariant 8 (Discovery Error in Status Reporting):** When path discovery fails:
  * Human CLI: `Monitored Directory: Not Found (Use --journal-dir or $ED_JOURNAL_DIR)`
  * Machine JSON: `{"is_active": false, "monitored_directory": null, "discovery_error": "No valid journal directory detected"}`
* **Invariant 9 (Path Discovery Audit Event):** If path discovery fails or encounters inaccessible paths, a structured `WatcherAuditEventDTO` must be emitted under topic `telemetry.audit` with `action: "path_discovery_failed"`.
* **Invariant 10 (Operator Configuration Surface & Environment Precedence):** `ed-telemetry serve` must expose full operator controls via explicit CLI flags backed by standard environment variables (`$ED_*`) following strict evaluation precedence (`CLI Flag > Environment Variable > OS Default / Auto-Discovery`):
  * `--journal-dir PATH` / `ED_JOURNAL_DIR`: Overrides automated journal discovery.
  * `--db-path PATH` / `ED_DB_PATH`: Overrides default SQLite storage location.
  * `--poll-interval SEC` / `ED_POLL_INTERVAL`: Configures watcher heartbeat/fallback poll interval.
  * `--host IP` / `ED_HTTP_HOST`: Configures HTTP server interface binding.
  * `--port INT` / `ED_HTTP_PORT`: Configures HTTP server port.
  * `--log-level LEVEL` / `ED_LOG_LEVEL`: Configures logging verbosity.
  * `--log-file PATH` / `ED_LOG_FILE`: Configures rotating file log path.

## 5. Consequences

* **Positive:**
  * Clean operating system hygiene: No `.cache` directory littering operator working trees.
  * Consistent event queries: Historical queries access the same SQLite database regardless of where the command was run.
  * Reliable CLI commands: `status`, `logs`, and `tail` work accurately both when the daemon is running and in standalone mode.
  * Explicit operator observability: Clear startup banner eliminates ambiguity regarding which Proton prefix or Windows directory is being watched.
  * Actionable failure diagnostics: Operators immediately receive remediation instructions when discovery fails rather than wondering why events are missing.
* **Negative / Trade-offs:**
  * Adds standard-library HTTP polling and streaming logic to `CliTelemetryAdapter`.
