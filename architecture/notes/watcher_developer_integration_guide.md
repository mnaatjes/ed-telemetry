---
title: "Watcher Developer Integration Guide and Implementation Examples"
tags: ["architecture", "notes", "watcher", "integration", "examples", "developer-guide"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# Watcher Developer Integration Guide and Implementation Examples

This document demonstrates how to instantiate, configure, and execute the `ed_watcher` subsystem from a developer's perspective. It covers:
1. Low-level direct execution using `WatcherReactor`.
2. High-level execution using the lifecycle-managed `JournalWatcher` port adapter ([ADR 0009](../adr/0009_watcher_port_adapter_and_threaded_lifecycle.md)).
3. Full application execution through the `ed_app.bootstrap` composition root.
4. Handling and rendering realtime event bursts.

---

## 1. Pattern A: Direct Low-Level Reactor Execution (Single Thread / Generator)

If you are developing a standalone script, benchmark, or offline log processor, you can wire the internal components directly:

```python
"""scripts/run_direct_reactor.py

Directly instantiate the reactor loop and consume events via generator.
"""

from pathlib import Path
import time
from ed_watcher.path_discoverer import PathDiscoverer
from ed_watcher.selector import JournalSelector, StreamPosition
from ed_watcher.snapshots.identifier import SnapshotIdentifier
from ed_watcher.snapshots.registry import SnapshotRegistry
from ed_watcher.engine.reactor import WatcherReactor
from ed_watcher.engine.envelopes import FileIngestionEvent, WatcherAuditEvent, FileKind


def main() -> None:
    # 1. Discover the game directory (or pass Path("/custom/path"))
    discoverer = PathDiscoverer()
    journal_dir = discoverer.discover_journal_directory()
    print(f"[*] Monitoring game directory: {journal_dir}")

    # 2. Initialize candidate selectors and registries
    selector = JournalSelector(journal_dir)
    registry = SnapshotRegistry()
    identifier = SnapshotIdentifier(journal_dir, registry=registry)

    # 3. Create the reactive reactor
    reactor = WatcherReactor(
        journal_dir=journal_dir,
        selector=selector,
        snapshot_identifier=identifier,
        stream_position=StreamPosition.LATEST,  # Start at end of active log
        poll_interval=0.5,  # 500ms heartbeat ticker
    )

    print("[*] Starting reactive reactor loop. Press Ctrl+C to stop...")
    try:
        # 4. Stream envelopes as they occur
        for item in reactor.run():
            if isinstance(item, FileIngestionEvent):
                if item.kind == FileKind.JOURNAL:
                    print(f"[JOURNAL] {item.file_path.name} @ byte {item.read_offset}: {item.payload}")
                else:
                    print(
                        f"[SNAPSHOT] {item.file_path.name} (version {item.snapshot_version}): {len(item.payload)} bytes"
                    )
            elif isinstance(item, WatcherAuditEvent):
                print(f"[AUDIT] {item.action.value} -> {item.details}")
    except KeyboardInterrupt:
        print("\n[*] Stopping reactor...")
        reactor.stop()


if __name__ == "__main__":
    main()
```

---

## 2. Pattern B: Threaded Port Adapter Execution (Planned ADR 0009)

In an application service, GUI, or daemon, you do not want to block the main thread. The `JournalWatcher` adapter runs the reactor inside a managed background thread:

```python
"""scripts/run_threaded_watcher.py

Execute the watcher asynchronously via the JournalWatcher port adapter.
"""

import time
from pathlib import Path
from ed_watcher.watcher import JournalWatcher
from ed_watcher.selector import StreamPosition
from ed_watcher.engine.envelopes import FileIngestionEvent, WatcherAuditEvent


def on_telemetry_event(event: FileIngestionEvent) -> None:
    """Callback triggered whenever new journal lines or snapshot files arrive."""
    print(f"[DATA] Received {event.kind.value} from {event.file_path.name}: {event.payload[:60]}...")


def on_audit_event(event: WatcherAuditEvent) -> None:
    """Callback triggered for internal watcher lifecycle and performance events."""
    print(f"[HEALTH] {event.action.value} on {event.target_path}")


def main() -> None:
    # 1. Instantiate the watcher with optional custom overrides
    # Zero arguments uses auto PathDiscoverer and default settings.
    watcher = JournalWatcher(
        stream_position=StreamPosition.LATEST,
        on_event=on_telemetry_event,
        on_audit=on_audit_event,
    )

    # 2. Start background thread (non-blocking)
    print("[*] Starting JournalWatcher background worker...")
    watcher.start()
    assert watcher.is_active

    # 3. Main thread is free to do other work (TUI, API server, or sleep)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[*] Halting watcher...")
        watcher.stop()
        print("[*] Watcher cleanly stopped.")


if __name__ == "__main__":
    main()
```

---

## 3. Pattern C: Full System Execution via Application Composition Root

In production, neither your CLI nor your entry point interacts with `ed_watcher` directly. Instead, they interact with `TelemetryEngine` created by `ed_app.bootstrap`:

```python
"""scripts/run_telemetry_engine.py

Instantiate and execute the full system through the composition root.
"""

import time
from ed_app.bootstrap import build_engine


def main() -> None:
    # 1. Build the engine (wires JournalWatcher and EgressTransmitters)
    # Guaranteed side-effect free: does not start threads or bind sockets yet.
    engine = build_engine()

    # 2. Start the entire application pipeline
    print("[*] Starting TelemetryEngine...")
    engine.start()
    print(f"[*] Engine status: running={engine.is_running}")

    try:
        # Engine coordinates watcher -> domain parser -> egress routers
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[*] Stopping TelemetryEngine...")
        engine.stop()
        print("[*] Engine shutdown complete.")


if __name__ == "__main__":
    main()
```

---

## 4. Realtime Event Burst Rendering (Developer Observation Tool)

To observe high-frequency telemetry bursts during in-game events (such as jumping to hyperspace, which emits dozens of journal events and toggles `Status.json` flags), you can pipe callbacks into a rich terminal view or metrics tracker:

```python
"""scripts/render_event_bursts.py

Render real-time telemetry throughput and event bursts using Rich tables.
"""

from rich.live import Live
from rich.table import Table
from rich.console import Console
import time
from ed_watcher.watcher import JournalWatcher
from ed_watcher.engine.envelopes import FileIngestionEvent

console = Console()
event_counts = {"JOURNAL": 0, "SNAPSHOT": 0, "TOTAL_BYTES": 0}
recent_events = []


def handle_event(event: FileIngestionEvent) -> None:
    event_counts[event.kind.value] += 1
    event_counts["TOTAL_BYTES"] += event.payload_bytes
    recent_events.append((event.kind.value, event.file_path.name, event.payload[:50]))
    if len(recent_events) > 10:
        recent_events.pop(0)


def generate_dashboard() -> Table:
    table = Table(title="Elite Dangerous Telemetry Live Ingestion Feed")
    table.add_column("Type", justify="center", style="cyan")
    table.add_column("File", style="magenta")
    table.add_column("Preview", style="green")

    for kind, filename, preview in reversed(recent_events):
        table.add_row(kind, filename, preview)
    return table


def main() -> None:
    watcher = JournalWatcher(on_event=handle_event)
    watcher.start()

    with Live(generate_dashboard(), refresh_per_second=4, console=console) as live:
        try:
            while True:
                time.sleep(0.25)
                live.update(generate_dashboard())
        except KeyboardInterrupt:
            watcher.stop()


if __name__ == "__main__":
    main()
```
