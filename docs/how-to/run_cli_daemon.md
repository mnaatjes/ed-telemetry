---
title: "How to Run the CLI Telemetry Daemon"
tags: ["how-to", "cli", "operator-guide", "daemon", "execution"]
created_at: "2026-10-06"
last_updated_at: "2026-10-25"
---

# How to Run the CLI Telemetry Daemon

This practical runbook guides operators and integrators through installing, running, and managing the `ed-telemetry` CLI daemon across Windows, Linux, and Steam Deck.

---

## 1. Prerequisites & Installation

Ensure Python 3.11 or newer is installed on your workstation or host system.

1. Create and activate a dedicated virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install the package in editable mode:
   ```bash
   pip install -e .
   ```

---

## 2. Running the Telemetry Daemon (`serve`)

The `serve` command starts the background filesystem watcher, activates SQLite WAL mode persistence, and binds the HTTP REST and Server-Sent Events (SSE) server.

### Default Execution
```bash
ed-telemetry serve
```

Expected startup output:
```text
Starting ed-telemetry daemon on 127.0.0.1:8080...
Discovered Journal Directory: /home/pilot/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous (Source: LinuxProtonStrategy)
Active Journal: Journal.2026-10-25T142610.01.log
HTTP/SSE API listening on http://127.0.0.1:8080/api/v1
Press Ctrl+C to stop.
```

### Discovery Failure & Fast-Fail Remediation
If automated strategies cannot locate the Elite Dangerous journal directory, the daemon aborts with POSIX exit code `1` and outputs actionable remediation guidance:

```text
[ERROR] Failed to discover Elite Dangerous journal directory.
Evaluated strategies: Windows Registry, Steam Proton (AppID 359320), Default User Paths.
Remediation:
  1. Pass the path explicitly: ed-telemetry serve --journal-dir "/path/to/journal/folder"
  2. Or set environment variable: export ED_JOURNAL_DIR="/path/to/journal/folder"
```

### Configuration Options & Environment Precedence
The runtime evaluates settings with the following precedence: `CLI Flag > Environment Variable > OS Default / Auto-Discovery`.

| Setting | CLI Flag (`serve`) | Environment Variable | Default Value | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Journal Directory** | `--journal-dir PATH` | `ED_JOURNAL_DIR` | Auto-discovered (Proton/Registry) | Root directory containing `Journal.*.log` and `Status.json`. |
| **HTTP Host** | `--host IP` | `ED_HTTP_HOST` | `127.0.0.1` | Network interface (`0.0.0.0` for remote LAN access). |
| **HTTP Port** | `--port INT` | `ED_HTTP_PORT` | `8080` | Port for REST and SSE streaming endpoints. |
| **Log Level** | `--log-level LEVEL` | `ED_LOG_LEVEL` | `INFO` | Verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| **Rotating Log File** | `--log-file PATH` | `ED_LOG_FILE` | Standard OS log path | Explicit file path for rotating disk logs. |
| **SQLite DB Path** | `--db-path PATH` | `ED_DB_PATH` | Standard OS data path | SQLite database file storing telemetry events. |
| **Poll Interval** | `--poll-interval SEC` | `ED_POLL_INTERVAL` | `1.0s` (Win) / `0.5s` (Linux) | Watcher reactor heartbeat/fallback tick rate. |


---

## 3. Querying Operational Status (`status`)

Check watcher state, journal directories, and game cockpit telemetry while the daemon is running or standalone.

### Watcher Operational State
```bash
ed-telemetry status
```

Expected output:
```text
Watcher State: Idle
Monitored Directory: /home/user/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous
Active Journal: Journal.2026-10-25T140000.01.log
```

### Cockpit Status (`Status.json`)
Inspect player status, gear state, pips, and flags:
```bash
ed-telemetry status game
```

Expected output:
```text
Game Status Snapshot: Found
Path: /path/to/Saved Games/.../Status.json
Timestamp: 2026-10-25T16:00:00+00:00
```

### JSON Output
All status commands support `--json` for scripted consumption:
```bash
ed-telemetry status --json
ed-telemetry status game --json
```

---

## 4. Querying Historical Telemetry (`events`)

Retrieve telemetry payloads persisted to the SQLite database:

```bash
# Query recent events across all topics
ed-telemetry events --limit 10

# Filter specifically for journal events
ed-telemetry events --topic telemetry.journal --limit 20

# Query events newer than a specific ID
ed-telemetry events --since-id 150 --limit 50

# Output as formatted JSON
ed-telemetry events --json
```

---

## 5. Inspecting Diagnostic Application Logs (`logs`)

Inspect operational logs with automatic daemon probing and offline disk file fallback:

```bash
# Query recent logs (default 50)
ed-telemetry logs

# Filter by minimum log severity
ed-telemetry logs --level WARNING

# Limit record count
ed-telemetry logs --limit 10

# Output as formatted JSON
ed-telemetry logs --json
```

* **When Daemon is Online:** `ed-telemetry logs` queries the running daemon's in-memory ring buffer via `GET /api/v1/diagnostics/logs`.
* **When Daemon is Offline:** `ed-telemetry logs` falls back to reading and parsing recent entries from the rotating log file on disk (`resolve_default_log_path()`).

---

## 6. Streaming Live Events (`tail`)

Follow real-time telemetry and audit events from the terminal:

```bash
# Follow all outbound events
ed-telemetry tail

# Filter specifically for watcher error and control transitions
ed-telemetry tail --topic telemetry.audit

# Stream as raw JSON envelopes
ed-telemetry tail --json
```

* **When Daemon is Online:** Connects to the HTTP/SSE streaming endpoint (`/api/v1/stream`) and yields inbound events in real time.
* **When Daemon is Offline:** Activates a local, standalone `FileSystemWatcher` streaming lifecycle, streaming events directly from the journal files until terminated with `Ctrl+C`.
