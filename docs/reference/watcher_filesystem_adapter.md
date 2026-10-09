---
title: "Watcher FileSystemWatcher Adapter Reference"
tags: ["reference", "watcher", "adapter", "threading", "lifecycle"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# Watcher FileSystemWatcher Adapter Reference

The `FileSystemWatcher` adapter (`ed_watcher.watcher.FileSystemWatcher`) is the canonical driving adapter implementing `ed_domain.ports.WatcherPort`. It coordinates cross-platform OS path discovery, candidate sorting, snapshot casing normalization, and the reactive reactor loop within a managed background daemon thread.

---

## 1. Interface Signature

```python
from pathlib import Path
from ed_domain.ports.watcher import WatcherPort, IngestionEventHandler, AuditEventHandler
from ed_watcher.selector import StreamPosition
from ed_watcher.snapshots.registry import SnapshotRegistry


class FileSystemWatcher(WatcherPort):
    def __init__(
        self,
        journal_dir: Path | None = None,
        snapshot_registry: SnapshotRegistry | None = None,
        stream_position: StreamPosition = StreamPosition.TAIL,
        poll_interval: float | None = None,
        on_event: IngestionEventHandler | None = None,
        on_audit: AuditEventHandler | None = None,
        join_timeout: float = 5.0,
    ) -> None: ...
```

---

## 2. Constructor Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `journal_dir` | `Optional[Path]` | `None` | Explicit filesystem path. When omitted, uses `PathDiscoverer().discover_journal_directory()`. |
| `snapshot_registry` | `Optional[SnapshotRegistry]` | `None` | Custom snapshot definitions. When omitted, uses standard `SnapshotRegistry()`. |
| `stream_position` | `StreamPosition` | `StreamPosition.TAIL` | Initial seek mode (`TAIL` for live monitoring, `HEAD` for full historical replay). |
| `poll_interval` | `Optional[float]` | `None` | Polling tick interval in seconds (defaults to 1.0s on Windows, 0.5s on Wine/Linux). |
| `on_event` | `Optional[IngestionEventHandler]` | `None` | Initial callback receiving `FileIngestionEvent` envelopes. |
| `on_audit` | `Optional[AuditEventHandler]` | `None` | Initial callback receiving `WatcherAuditEvent` diagnostics. |
| `join_timeout` | `float` | `5.0` | Maximum seconds to wait when joining the background thread during `stop()`. |

---

## 3. Lifecycle Methods

### `register_event_handler(handler: IngestionEventHandler) -> None`
Appends a callback handler invoked synchronously on the worker thread when new `FileIngestionEvent` items arrive. Handlers are deduplicated.

### `register_audit_handler(handler: AuditEventHandler) -> None`
Appends a callback handler invoked synchronously on the worker thread when internal `WatcherAuditEvent` items are emitted.

### `start() -> None`
Asynchronously initializes the reactor pipeline and launches a background daemon thread (`ed-watcher-reactor`). Idempotent when called repeatedly while active.

### `stop() -> None`
Signals shutdown to the reactor loop and joins the worker thread within `join_timeout` seconds. Cleans up file handles. Idempotent when called repeatedly while inactive.

### `is_active -> bool`
Read-only property returning `True` if the worker thread is actively polling.

### `journal_dir -> Optional[Path]`
Read-only property returning the resolved directory currently being watched.
