---
title: "Diagnostic Logging and Persistent Storage Reference"
tags: ["reference", "logging", "storage", "sqlite", "diagnostics", "audit"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# Diagnostic Logging and Persistent Storage Reference

This technical reference specifies the filesystem paths, rotation policies, thread safety contracts, and schemas governing diagnostic logging and SQLite event storage.

---

## 1. Cross-Platform Log Paths & Rotation Policy

Log file paths are resolved dynamically by `ed_telemetry.bootstrap.container.resolve_default_log_path()`:

| Platform | Default Path | Environment Variable Overrides |
| :--- | :--- | :--- |
| **Windows** | `%LOCALAPPDATA%\ed-telemetry\logs\ed-telemetry.log` | `LOCALAPPDATA`, `USERPROFILE` |
| **Linux / Steam Deck** | `${XDG_STATE_HOME:-~/.local/state}/ed-telemetry/ed-telemetry.log` | `XDG_STATE_HOME`, `HOME` |

### Rotation Constraints
* **Handler:** Standard library `logging.handlers.RotatingFileHandler`.
* **File Size Threshold:** `maxBytes = 5_242_880` (5 MB).
* **Backup Retained:** `backupCount = 3` (retaining up to 20 MB total historical log storage).
* **Encoding:** `utf-8`.
* **Format:** `%(asctime)s [%(levelname)s] %(name)s: %(message)s` (`%Y-%m-%dT%H:%M:%S`).

---

## 2. In-Memory Diagnostic Ring Buffer

Implemented in `ed_telemetry.adapters.driven.logging.buffer.DiagnosticLogBuffer`:
* **Inheritance:** `logging.Handler`, `DiagnosticLogPort`.
* **Thread Safety:** Protected via reentrant locking (`threading.Lock()`).
* **Storage:** Double-ended queue (`collections.deque(maxlen=1000)`).
* **Filtering:** Evaluated against numeric log levels (`DEBUG: 10`, `INFO: 20`, `WARNING: 30`, `ERROR: 40`, `CRITICAL: 50`).

### DTO Schemas

#### `DiagnosticLogRecordDTO`
```python
@dataclass(frozen=True, slots=True)
class DiagnosticLogRecordDTO(DataTransferObject):
    timestamp: datetime
    level: str
    logger_name: str
    message: str
```

#### `DiagnosticLogSnapshotDTO`
```python
@dataclass(frozen=True, slots=True)
class DiagnosticLogSnapshotDTO(DataTransferObject):
    records: tuple[DiagnosticLogRecordDTO, ...]
    total_retained: int
```

---

## 3. SQLite Telemetry Persistence (WAL Mode)

Managed by `ed_telemetry.adapters.driven.persistence.sqlite_adapter.SqlitePersistenceManager`:
* **Default Database Path:** `.cache/telemetry.db`.
* **Journal Mode:** `PRAGMA journal_mode=WAL;` (Write-Ahead Logging for concurrent reader/writer access).
* **Synchronous Setting:** `PRAGMA synchronous=NORMAL;`.
* **Schema:**
  ```sql
  CREATE TABLE IF NOT EXISTS telemetry_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT UNIQUE NOT NULL,
      topic TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      raw_hash TEXT,
      payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_telemetry_topic ON telemetry_events(topic);
  CREATE INDEX IF NOT EXISTS idx_telemetry_created_at ON telemetry_events(created_at);
  ```

---

## 4. Live Audit Event Bubbling (`telemetry.audit`)

When internal filesystem watcher operational transitions or errors occur, `WatcherAuditEventDTO` items are serialized to JSON and emitted under topic `telemetry.audit`.

### Payload Schema
```json
{
  "timestamp": "2026-10-25T16:00:00+00:00",
  "action": "file_rotation",
  "target_path": "/path/to/Journal.log",
  "detail": "Rotated to part 2"
}
```
Metadata attached: `(("action", "<action_type>"),)`
