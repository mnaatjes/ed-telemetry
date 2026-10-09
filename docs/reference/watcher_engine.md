---
title: "Reference: ed_watcher Ingestion Engine and Reactive Reactor API"
tags: ["reference", "watcher", "reactor", "engine", "streaming", "freshness", "api"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# Reference: ed_watcher Ingestion Engine and Reactive Reactor API

This reference describes the classes, protocols, state machines, and event envelopes provided by the `ed_watcher.engine` subsystem for tailing journal streams, reading snapshot heartbeats, evaluating content freshness, and driving lifecycle events.

Governed by [ADR 0008](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0008_file_ingestion_io_freshness_and_concurrency.md) and [SDD-006](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/designs/0006_file_ingestion_io_and_reactive_reactor.md).

---

## 1. Primary Class: `WatcherReactor`

```python
class WatcherReactor:
    def __init__(
        self,
        journal_dir: Path,
        stream_position: StreamPosition = StreamPosition.TAIL,
        queue_capacity: int = 256,
        data_listener: Callable[[FileIngestionEvent], None] | None = None,
        audit_listener: Callable[[WatcherAuditEvent], None] | None = None,
    ) -> None: ...
```

The unified execution engine driving file ingestion, freshness evaluation, part rollover transitions, and event emission.

### Methods

#### `start()`
Initializes active journal streaming and transitions reactor to running state.

#### `stop()`
Finalizes and closes active file handles cleanly.

#### `step_once() -> Sequence[FileIngestionEvent]`
Executes one complete evaluation tick:
1. Dispatches any pending commands from the inbound queue.
2. Checks for journal successor rollover.
3. Steps the active journal tailer.
4. Checks the `Status.json` cockpit heartbeat.
5. Sweeps auxiliary snapshots for fresh content.

#### `submit_hint(command: WatcherIngestCommand) -> bool`
Submits an operational hint across the feedback boundary into the bounded command queue. Returns `True` if enqueued, or `False` if dropped due to queue congestion.

#### `get_queue_metrics() -> ReactorQueueMetrics`
Returns operational metrics on inbound command queue depth, capacity, high-water mark, and drop counts.

---

## 2. Event Envelopes

### Data Plane: `FileIngestionEvent`

```python
@dataclass(frozen=True)
class FileIngestionEvent:
    event_id: UUID
    timestamp: datetime  # UTC ISO 8601
    file_kind: FileKind  # JOURNAL, STATUS, SNAPSHOT
    target_path: Path
    raw_payload: bytes
    start_offset: int
    end_offset: int
    line_number: int | None
    part: int | None
    raw_hash: str  # 64-bit BLAKE2b digest
```

Emitted upon extracting a valid, structurally complete raw byte slice from disk.

### Control Plane: `WatcherAuditEvent`

```python
@dataclass(frozen=True)
class WatcherAuditEvent:
    timestamp: datetime
    action: WatcherAuditAction
    target_path: Path
    detail: str = ""
```

Emitted on internal lifecycle transitions (`PART_ROLLOVER`, `LINE_QUARANTINED`, `RETRY_BACKOFF`, `HINT_ENQUEUED`, `SELECTED`, etc.).

---

## 3. Streaming & Reading Components

### `JournalStreamContext`
Isolated, per-file streaming state machine tracking `handle`, `last_valid_offset`, `current_line_number`, and fragment buffers.
* **`open(path, part, position) -> JournalStreamContext`**: Opens file and applies initial `StreamPosition` policy (`HEAD` $\to 0$; `TAIL` $\to$ `st_size`).

### `JournalTailer`
Reads delta slices from `JournalStreamContext` enforcing monotonic forward seek (`handle.seek(last_valid_offset, os.SEEK_SET)`) and a 64 KB burst buffer. Bounded by a two-factor fragment quarantine circuit breaker (5.0s stagnant timeout or $>5\text{ MB}$ ceiling).

### `SnapshotReader`
Whole-reads JSON state snapshots with 20ms debouncing, structural boundary checking (`startswith(b'{') and endswith(b'}')`), and exponential backoff retries (20ms, 40ms, 80ms) against game truncation races.

### `SnapshotFreshnessTracker`
Deduplicates snapshot reads via 64-bit BLAKE2b content hashes. Discards duplicate payloads silently without emitting downstream events.

---

## 4. Inbound Port Contracts

### `WatcherIngestCommand`

```python
@dataclass(frozen=True)
class WatcherIngestCommand:
    action: WatcherHintAction  # HINT_SNAPSHOT, HINT_ROLLOVER, HINT_DIRECTORY_SCAN
    target_name: str | None = None
    priority: bool = False
```

---

## 5. Usage Example

```python
from pathlib import Path
from ed_watcher import (
    PathDiscoverer,
    StreamPosition,
    WatcherReactor,
    FileIngestionEvent,
    WatcherAuditEvent,
)


def on_data_event(event: FileIngestionEvent) -> None:
    print(f"[{event.file_kind.upper()}] Read {len(event.raw_payload)} bytes: {event.raw_payload[:40]}...")


def on_audit_event(event: WatcherAuditEvent) -> None:
    print(f"[AUDIT: {event.action}] {event.detail}")


# 1. Discover journal directory
dir_path = PathDiscoverer().discover_journal_directory().path

# 2. Boot reactor
reactor = WatcherReactor(
    journal_dir=dir_path,
    stream_position=StreamPosition.HEAD,
    data_listener=on_data_event,
    audit_listener=on_audit_event,
)
reactor.start()

# 3. Step reactor
emitted = reactor.step_once()
print(f"Emitted {len(emitted)} events on first step.")

reactor.stop()
```
