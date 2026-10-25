---
title: "How to Inspect Logs and Runtime Diagnostics"
tags: ["how-to", "logging", "diagnostics", "troubleshooting", "audit", "runbook"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# How to Inspect Logs and Runtime Diagnostics

This runbook guides operators on locating on-disk rotating logs, querying in-memory diagnostic snapshots, and streaming real-time error and audit transitions.

---

## 1. Locating Rotating On-Disk Log Files

`ed-telemetry` writes rotating logs using standard library `RotatingFileHandler` with a **5 MB size limit** and **3 backup files** (`ed-telemetry.log`, `ed-telemetry.log.1`, etc.).

### Windows Standard Log Location
On Windows hosts, logs reside under the operator's `%LOCALAPPDATA%` tree:
```text
%LOCALAPPDATA%\ed-telemetry\logs\ed-telemetry.log
```
*Typical Path:* `C:\Users\<Username>\AppData\Local\ed-telemetry\logs\ed-telemetry.log`

### Linux / Steam Deck Standard Log Location
On Linux or Steam Deck systems, logs adhere to the XDG State specification:
```text
${XDG_STATE_HOME:-~/.local/state}/ed-telemetry/ed-telemetry.log
```
*Typical Path:* `/home/<user>/.local/state/ed-telemetry/ed-telemetry.log`

---

## 2. Inspecting Logs via CLI (`ed-telemetry logs`)

The daemon maintains an in-memory ring buffer capturing the most recent application log records.

### View Recent Logs
```bash
ed-telemetry logs
```

### Filter by Severity Level
Filter out noisy trace/debug messages to view only warnings and errors:
```bash
ed-telemetry logs --level WARNING
```

### Limit Record Count
```bash
ed-telemetry logs --limit 100
```

### JSON Export
Format log records as structured JSON for log aggregation or automated parsing:
```bash
ed-telemetry logs --level ERROR --json
```

Example JSON output:
```json
{
  "records": [
    {
      "timestamp": "2026-10-25T16:45:00.123456+00:00",
      "level": "ERROR",
      "logger_name": "ed_telemetry.adapters.driven.watcher.engine.tailer",
      "message": "File read permission denied on Journal.2026-10-25T140000.01.log"
    }
  ],
  "total_retained": 1
}
```

---

## 3. Querying Logs via HTTP REST API

When the daemon is running (`ed-telemetry serve`), logs can be fetched over HTTP:

```bash
# Query all recent logs
curl http://127.0.0.1:8080/api/v1/diagnostics/logs

# Filter by minimum level and limit
curl "http://127.0.0.1:8080/api/v1/diagnostics/logs?min_level=WARNING&limit=25"
```

---

## 4. Streaming Real-Time Operational & Error Events

Operational transitions (file rotation, truncated file recovery) and unrecoverable parser errors are bubbled to the egress stream under topic `telemetry.audit`.

### Live Terminal Tailing
Follow audit events live in your console:
```bash
ed-telemetry tail --topic telemetry.audit
```

### Live SSE HTTP Subscription
Subscribe using `curl`:
```bash
curl -N http://127.0.0.1:8080/api/v1/stream
```

Example SSE frame:
```text
data: {"topic": "telemetry.audit", "timestamp": "2026-10-25T16:45:10.500000+00:00", "payload": "{\"timestamp\": \"2026-10-25T16:45:10.500000+00:00\", \"action\": \"file_rotation\", \"target_path\": \"/path/to/Journal.log\", \"detail\": \"Rotated to part 2\"}"}
```
