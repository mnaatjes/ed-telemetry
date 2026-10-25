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
HTTP/SSE API listening on http://127.0.0.1:8080/api/v1
Press Ctrl+C to stop.
```

### Custom Host, Port, and Logging Options
You can customize the network binding and logging verbosity:
```bash
ed-telemetry serve --host 0.0.0.0 --port 9000 --log-level DEBUG --log-file /tmp/telemetry.log
```

* `--host`: Interface to bind (default: `127.0.0.1`).
* `--port`: Port number (default: `8080`).
* `--log-level`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
* `--log-file`: Explicit destination file for rotating logs. When omitted, writes to the standard OS log location.

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

## 5. Streaming Live Events (`tail`)

Follow real-time telemetry and audit events from the terminal:

```bash
# Follow all outbound events
ed-telemetry tail

# Filter specifically for watcher error and control transitions
ed-telemetry tail --topic telemetry.audit

# Stream as raw JSON envelopes
ed-telemetry tail --json
```

Press `Ctrl+C` to terminate the stream.
