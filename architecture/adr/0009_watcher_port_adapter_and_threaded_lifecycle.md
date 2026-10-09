---
title: "ADR 0009: Watcher Port Adapter and Threaded Lifecycle Management"
status: "accepted"
date: "2026-10-09"
tags: ["architecture", "adr", "watcher", "adapter", "port", "threading", "lifecycle", "madr"]
---

# ADR 0009: Watcher Port Adapter and Threaded Lifecycle Management

## 1. Context and Problem Statement

With the completion of the core ingestion mechanics in `ed_watcher`:
- **Path Discovery** ([ADR 0004](0004_os_path_discovery_and_filesystem_research_framework.md)) resolves the game directory cross-platform.
- **Journal Candidate Selection** ([ADR 0006](0006_active_journal_candidate_selection_and_sorting.md)) isolates active logs and handles session rollover.
- **Snapshot Resolution** ([ADR 0007](0007_status_and_snapshot_file_identification.md)) maps and case-normalizes discrete game state files.
- **Unified Reactive Reactor Engine** ([ADR 0008](0008_file_ingestion_io_freshness_and_concurrency.md)) manages non-blocking byte tailing, zero-byte truncation guards, and yields typed event envelopes (`FileIngestionEvent`, `WatcherAuditEvent`).

However, `ed_watcher` currently terminates at `WatcherReactor.run()`, which is a synchronous generator loop. The outer interface of `ed_watcher`—currently named `JournalWatcher` in `packages/ed_watcher/watcher.py`—remains a skeletal boolean toggle stub left over from the walking skeleton ([ADR 0003](0003_minimal_walking_skeleton_and_bootstrap_contract.md)).

This presents three key architectural defects:
1. **Misleading Nomenclature:** The class name `JournalWatcher` implies it only watches `.log` journal files, whereas the subsystem actually monitors the entire telemetry stack: appending journal streams, the 1Hz `Status.json` cockpit heartbeat, and auxiliary station/menu state snapshots.
2. **Hollow Port Contract:** The abstract port contract `WatcherPort` in `packages/ed_domain/ports/watcher.py` specifies only `start() -> None` and `stop() -> None` without a mechanism for consumer event dispatch or error propagation.
3. **Missing Threaded Lifecycle Binding:** `WatcherReactor.run()` is a blocking generator. The driving adapter must manage background worker threads, clean start/stop synchronization, and bridge filesystem parameters (`Path`, `SnapshotRegistry`) into the pure domain port.

---

## 2. Decision Drivers

* **Clean Hexagonal Isolation:** `ed_watcher` is an inbound driving adapter; it must implement `WatcherPort` without leaking OS-specific primitives (`watchdog`, file descriptors, Windows paths) into `ed_domain`.
* **Ubiquitous Domain Nomenclature:** The adapter name must accurately reflect its comprehensive responsibility: monitoring all telemetry files across the game directory (journals, status, and auxiliary snapshots).
* **Non-Blocking Host Process:** Invoking `start()` must not block the calling application process or CLI entry point.
* **Deterministic Shutdown:** Calling `stop()` must reliably terminate the reactor loop, flush resources, close file descriptors, and join threads within a deterministic timeout without hanging the process.
* **Ergonomic Developer Integration:** Instantiating the watcher in a standalone script or consumer service must require zero configuration defaults (`FileSystemWatcher()`) while offering granular overrides (`journal_dir`, `snapshot_registry`, `poll_interval`, `stream_position`, `on_event`, `on_audit`).

---

## 3. Decision Outcome

Chosen Option: **Callback-Driven Threaded `FileSystemWatcher` Adapter with Constructor Dependency Injection**.

We will:
1. Formalize `WatcherPort` in `ed_domain` to define strongly-typed event/audit subscription contracts.
2. Implement a production, thread-managed `FileSystemWatcher` adapter in `packages/ed_watcher/watcher.py` (superseding the `JournalWatcher` stub).
3. Keep physical filesystem configurations (`Path`, `SnapshotRegistry`, poll intervals) strictly in the adapter constructor, preserving total domain purity for `WatcherPort`.

---

### 3.1 Formal Port Contract (`packages/ed_domain/ports/watcher.py`)

The port contract defines callable protocol aliases and subscription methods while preserving Invariant A (Domain I/O purity):

```python
from typing import Any, Callable, Protocol, runtime_checkable

# Type aliases for event handlers
# Handlers accept unparsed event envelopes or domain payloads
IngestionEventHandler = Callable[[Any], None]
AuditEventHandler = Callable[[Any], None]


@runtime_checkable
class WatcherPort(Protocol):
    """Abstract contract for inbound telemetry driving adapters."""

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        """Register a callback for raw file ingestion events."""
        ...

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        """Register a callback for watcher operational audit events."""
        ...

    def start(self) -> None:
        """Start listening or polling for telemetry events asynchronously."""
        ...

    def stop(self) -> None:
        """Stop listening or polling and wait for background workers to exit."""
        ...

    @property
    def is_active(self) -> bool:
        """Return True if watcher is actively listening."""
        ...
```

---

### 3.2 Concrete Threaded Adapter (`packages/ed_watcher/watcher.py`)

The production adapter is named `FileSystemWatcher` to reflect that it monitors the complete directory stack (journals and snapshots).

#### Constructor Dependency Injection vs. Port Boundary
Operating system paths (`Path`) and filesystem snapshot configurations (`SnapshotRegistry`) are **physical infrastructure concerns**. Therefore, they are injected into the adapter's constructor rather than placed on `WatcherPort`:

```python
from pathlib import Path
from typing import Optional
import threading

from ed_domain.ports.watcher import WatcherPort, IngestionEventHandler, AuditEventHandler
from ed_watcher.path_discoverer import PathDiscoverer
from ed_watcher.selector import JournalSelector, StreamPosition
from ed_watcher.snapshots.registry import SnapshotRegistry
from ed_watcher.snapshots.identifier import SnapshotIdentifier
from ed_watcher.engine.reactor import WatcherReactor


class FileSystemWatcher(WatcherPort):
    """Concrete driving adapter monitoring journals and snapshots from the filesystem."""

    def __init__(
        self,
        journal_dir: Optional[Path] = None,
        snapshot_registry: Optional[SnapshotRegistry] = None,
        stream_position: StreamPosition = StreamPosition.LATEST,
        poll_interval: Optional[float] = None,
        on_event: Optional[IngestionEventHandler] = None,
        on_audit: Optional[AuditEventHandler] = None,
        join_timeout: float = 5.0,
    ) -> None:
        self._journal_dir = journal_dir
        self._snapshot_registry = snapshot_registry or SnapshotRegistry()
        self._stream_position = stream_position
        self._poll_interval = poll_interval
        self._join_timeout = join_timeout

        self._event_handlers: list[IngestionEventHandler] = []
        self._audit_handlers: list[AuditEventHandler] = []

        if on_event:
            self._event_handlers.append(on_event)
        if on_audit:
            self._audit_handlers.append(on_audit)

        self._thread: Optional[threading.Thread] = None
        self._reactor: Optional[WatcherReactor] = None
        self._is_active = False
```

#### Lifecycle State Management
1. **`start()` Lifecycle:**
   - If `journal_dir` was not injected, invokes `PathDiscoverer().discover_journal_directory()`.
   - Initializes `JournalSelector`, `SnapshotIdentifier`, and `WatcherReactor`.
   - Launches a background daemon thread: `threading.Thread(target=self._worker_loop, name="ed-watcher-reactor", daemon=True)`.
   - Sets `self._is_active = True`.
2. **Worker Loop Execution (`self._worker_loop`):**
   - Iterates through `for item in self._reactor.run(): ...`.
   - Dispatches `FileIngestionEvent` to all registered event handlers.
   - Dispatches `WatcherAuditEvent` to all registered audit handlers.
   - Wraps handler invocation in exception guards to prevent consumer errors from breaking the reactor loop.
3. **`stop()` Lifecycle:**
   - Invokes `self._reactor.stop()`.
   - Joins the worker thread with `self._thread.join(timeout=self._join_timeout)`.
   - Sets `self._is_active = False`.

---

### 3.3 Application Bootstrapping (`packages/ed_app/bootstrap.py`)

`ed_app.bootstrap.build_engine()` will instantiate `FileSystemWatcher` (with zero-arg auto-discovery defaults), register the engine's ingestion routing methods, and return a runnable `TelemetryEngine`.

---

## 4. Architectural Consequences

### Positive
* **Accurate Ubiquitous Language:** Renaming the adapter to `FileSystemWatcher` clarifies that it ingests both streaming journals and state snapshots.
* **Autonomous Sealing:** `packages/ed_watcher/` becomes an entirely closed, production-tested subsystem with zero remaining stubs.
* **Zero Main-Thread Blocking:** CLI, TUI, REST API, or MCP servers can call `engine.start()` and proceed with user interaction or HTTP request listening immediately.
* **Flexible Egress Routing:** Any consumer can attach custom callbacks (`on_event`) to capture live telemetry without modifying core files.

### Negative / Trade-Offs
* **Multi-Threading Considerations:** Callbacks dispatched by `FileSystemWatcher` execute on the background reactor thread. Downstream state mutators in `ed_domain` or `ed_app` must ensure thread-safe state transitions or post events to an application queue.

---

## 5. References
* [ADR 0001: Architectural Vision, Operational Concept, and CI-Enforced Modular Boundaries](0001_architectural_vision_and_operational_concept.md)
* [ADR 0003: Minimal Walking Skeleton and Bootstrap Verification Contract](0003_minimal_walking_skeleton_and_bootstrap_contract.md)
* [ADR 0008: File Ingestion Engine, Concurrency Guards, and Reactive Reactor](0008_file_ingestion_io_freshness_and_concurrency.md)
* [Developer Integration Guide](../notes/watcher_developer_integration_guide.md)
