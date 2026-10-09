---
title: "ADR 0009: Watcher Port Adapter and Threaded Lifecycle Management"
status: "proposed"
date: "2026-10-09"
tags: ["architecture", "adr", "watcher", "adapter", "port", "threading", "lifecycle", "madr"]
---

# ADR 0009: Watcher Port Adapter and Threaded Lifecycle Management

## 1. Context and Problem Statement

With the completion of the core ingestion mechanics in `ed_watcher`:
- **Path Discovery** ([ADR 0004](0004_os_path_discovery_and_filesystem_research_framework.md)) resolves the journal directory cross-platform.
- **Journal Candidate Selection** ([ADR 0006](0006_active_journal_candidate_selection_and_sorting.md)) isolates active logs and handles session rollover.
- **Snapshot Resolution** ([ADR 0007](0007_status_and_snapshot_file_identification.md)) maps and case-normalizes discrete game state files.
- **Unified Reactive Reactor Engine** ([ADR 0008](0008_file_ingestion_io_freshness_and_concurrency.md)) manages non-blocking byte tailing, zero-byte truncation guards, and yields typed event envelopes (`FileIngestionEvent`, `WatcherAuditEvent`).

However, `ed_watcher` currently terminates at `WatcherReactor.run()`, which is a synchronous generator loop. The outer interface of `ed_watcher`—defined by `JournalWatcher` in `packages/ed_watcher/watcher.py`—remains a skeletal boolean toggle stub left over from the walking skeleton ([ADR 0003](0003_minimal_walking_skeleton_and_bootstrap_contract.md)). Furthermore, the abstract port contract `WatcherPort` in `packages/ed_domain/ports/watcher.py` specifies only `start() -> None` and `stop() -> None` without a mechanism for consumer event dispatch or error propagation.

To seal `packages/ed_watcher/` as an autonomous, production-ready driving adapter, we must decide:
1. How `WatcherPort` in `ed_domain` defines the event dispatch contract without violating Invariant A (Domain I/O purity).
2. How the concrete adapter manages the background thread lifecycle, startup synchronization, and graceful shutdown joining.
3. How dependencies (`PathDiscoverer`, `WatcherReactor`, stream modes, overrides) are injected for developer testing versus production execution.

---

## 2. Decision Drivers

* **Clean Hexagonal Isolation:** `ed_watcher` is an inbound driving adapter; it must implement `WatcherPort` without leaking OS-specific primitives (`watchdog`, file descriptors, Windows paths) into `ed_domain`.
* **Non-Blocking Host Process:** Invoking `start()` must not block the calling application process or CLI entry point.
* **Deterministic Shutdown:** Calling `stop()` must reliably terminate the reactor loop, flush resources, close file descriptors, and join threads within a deterministic timeout without hanging the process.
* **Ergonomic Developer Integration:** Instantiating the watcher in a standalone script or consumer service must require zero configuration defaults (`JournalWatcher()`) while offering granular overrides (`journal_dir`, `poll_interval`, `stream_position`, `on_event`, `on_audit`).

---

## 3. Decision Outcome

Chosen Option: **Callback-Driven Threaded Port Adapter with Composition Dependency Injection**.

We will formalize `WatcherPort` in `ed_domain` to accept strongly-typed event callbacks, and implement a concrete, thread-managed `JournalWatcher` in `packages/ed_watcher/watcher.py` that orchestrates `PathDiscoverer`, `JournalSelector`, `SnapshotIdentifier`, and `WatcherReactor`.

---

### 3.1 Formal Port Contract (`packages/ed_domain/ports/watcher.py`)

The port contract will define callable protocol aliases and subscription methods while preserving Invariant A:

```python
from typing import Callable, Protocol, runtime_checkable

# Type aliases for event handlers
# Note: FileIngestionEvent and WatcherAuditEvent will be imported from
# a pure domain model package (or shared protocol representation)
IngestionEventHandler = Callable[[Any], None]
AuditEventHandler = Callable[[Any], None]


@runtime_checkable
class WatcherPort(Protocol):
    """Contract for inbound file and telemetry watchers."""

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

The production `JournalWatcher` adapter will encapsulate thread management:

1. **State & Synchronization:**
   - Managed via a dedicated daemon worker thread (`threading.Thread(name="ed-watcher-reactor", daemon=True)`).
   - Shutdown signaled via `threading.Event` coordinating `WatcherIngestReceiver.request_stop()`.
   - Thread join bounded by a deterministic timeout (`join_timeout: float = 5.0`).
2. **Construction Defaults:**
   - If `journal_dir` is omitted, automatically executes `PathDiscoverer().discover_journal_directory()`.
   - Accepts optional parameter overrides: `stream_position: StreamPosition`, `poll_interval: Optional[float]`, `on_event`, and `on_audit`.
3. **Execution Loop:**
   - The background worker executes `for item in reactor.run(): ...`.
   - Unpacks item into `FileIngestionEvent` or `WatcherAuditEvent` and dispatches immediately to registered handlers.
   - Exceptions inside handlers are caught or audited to prevent crashing the reactor loop.

---

### 3.3 Application Bootstrapping (`packages/ed_app/bootstrap.py`)

`ed_app.bootstrap.build_engine()` will instantiate the real `JournalWatcher`, register `TelemetryEngine` ingestion methods, and return an assembled, runnable engine ready for CLI or daemon execution.

---

## 4. Architectural Consequences

### Positive
* **Autonomous Sealing:** `packages/ed_watcher/` becomes an entirely closed, production-tested subsystem with zero remaining stubs.
* **Zero Main-Thread Blocking:** CLI, TUI, REST API, or MCP servers can call `engine.start()` and proceed with user interaction or HTTP request listening immediately.
* **Flexible Egress Routing:** Any consumer can attach custom callbacks (`on_event`) to capture live telemetry without modifying core files.

### Negative / Trade-Offs
* **Multi-Threading Considerations:** Callbacks dispatched by `JournalWatcher` execute on the background reactor thread. Downstream state mutators in `ed_domain` or `ed_app` must ensure thread-safe state transitions or post events to an application queue.

---

## 5. References
* [ADR 0001: Architectural Vision, Operational Concept, and CI-Enforced Modular Boundaries](0001_architectural_vision_and_operational_concept.md)
* [ADR 0003: Minimal Walking Skeleton and Bootstrap Verification Contract](0003_minimal_walking_skeleton_and_bootstrap_contract.md)
* [ADR 0008: File Ingestion Engine, Concurrency Guards, and Reactive Reactor](0008_file_ingestion_io_freshness_and_concurrency.md)
* [Developer Integration Guide](../notes/watcher_developer_integration_guide.md)
