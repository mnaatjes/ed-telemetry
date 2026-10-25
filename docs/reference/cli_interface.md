---
title: "CLI Command Reference"
tags: ["reference", "cli", "commands", "arguments"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# CLI Command Reference

This reference details the subcommands, command-line arguments, environment configurations, and POSIX exit codes of the `ed-telemetry` CLI adapter (`ed_telemetry.adapters.driving.cli.main`).

---

## 1. Top-Level Command Syntax

```bash
ed-telemetry [subcommand] [options]
```

When invoked with no arguments or `--help`, the CLI displays command assistance and exits with code `0`.

---

## 2. Subcommands

### 2.1 `serve`
Runs the background telemetry ingestion daemon, SQLite WAL event persistence, and HTTP/SSE API server.

```bash
ed-telemetry serve [--host HOST] [--port PORT] [--log-level LEVEL] [--log-file PATH] [--journal-dir PATH] [--db-path PATH] [--poll-interval SEC]
```

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | `127.0.0.1` | Network interface to bind for HTTP/SSE server (fallback: `$ED_HTTP_HOST`). |
| `--port` | `int` | `8080` | Port number for HTTP/SSE server (fallback: `$ED_HTTP_PORT`). |
| `--log-level` | `str` | `INFO` | Root logging level (fallback: `$ED_LOG_LEVEL`). |
| `--log-file` | `Path \| None` | `None` | Path to rotating log file (fallback: `$ED_LOG_FILE` or OS default). |
| `--journal-dir` | `Path \| None` | `None` | Explicit path to journal folder (fallback: `$ED_JOURNAL_DIR` or auto-discovery). |
| `--db-path` | `Path \| None` | `None` | SQLite database file path (fallback: `$ED_DB_PATH` or OS canonical data path). |
| `--poll-interval` | `float \| None` | `None` | Watcher poll interval in seconds (fallback: `$ED_POLL_INTERVAL` or OS default). |


---

### 2.2 `status`
Inspects operational state of the telemetry watcher or player cockpit. Automatically probes for an active daemon on `http://127.0.0.1:8080/api/v1/status` (or configured host/port) to report live `is_active: true` status, falling back to local inspection when offline.

```bash
ed-telemetry status [target] [--json]
```

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target` | `str \| None` | `None` | Optional target to inspect. Allowed value: `game` (queries `Status.json`). |
| `--json` | `flag` | `False` | Output payload as structured JSON to stdout. |

---

### 2.3 `events`
Queries historical telemetry events persisted to SQLite.

```bash
ed-telemetry events [--topic TOPIC] [--since-id ID] [--limit N] [--json]
```

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--topic` | `str \| None` | `None` | Filter by topic (e.g. `telemetry.journal`, `telemetry.status`, `telemetry.audit`). |
| `--since-id` | `int \| None` | `None` | Retrieve events strictly newer than given sequential database ID. |
| `--limit` | `int` | `20` | Maximum number of records to return. |
| `--json` | `flag` | `False` | Output payload as structured JSON to stdout. |

---

### 2.4 `logs`
Inspects diagnostic application logs. When a background daemon is running, queries its in-memory ring buffer via `GET /api/v1/diagnostics/logs`. When offline, falls back to parsing recent lines from the rotating log file on disk (`resolve_default_log_path()`).

```bash
ed-telemetry logs [--level LEVEL] [--limit N] [--json]
```

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--level` | `str \| None` | `None` | Minimum log severity to return (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `--limit` | `int` | `50` | Maximum number of log records to return. |
| `--json` | `flag` | `False` | Output payload as structured JSON to stdout. |

---

### 2.5 `tail`
Follows live telemetry events and error bubbling from the egress stream. When a background daemon is running, streams from `GET /api/v1/stream` via SSE. When offline, activates a local standalone `FileSystemWatcher` streaming lifecycle.

```bash
ed-telemetry tail [--topic TOPIC] [--json]
```

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--topic` | `str \| None` | `None` | Filter stream by topic (e.g. `telemetry.audit`). |
| `--json` | `flag` | `False` | Output events as one JSON line per event. |


---

## 3. Exit Codes

| Code | Meaning |
| :--- | :--- |
| `0` | Success / Clean execution or shutdown via `Ctrl+C`. |
| `1` | Configuration or runtime error (e.g., port not wired, missing database). |
| `2` | Command-line parsing error (invalid arguments or flags). |
