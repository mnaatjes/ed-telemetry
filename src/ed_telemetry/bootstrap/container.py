"""Composition root and dependency injection wiring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..adapters.driven.egress.transmitter import NullTransmitter
from ..adapters.driven.watcher.watcher import FileSystemWatcher
from ..core.use_cases.get_watcher_status import GetWatcherStatusUseCase
from ..core.use_cases.process_telemetry_stream import ProcessTelemetryStreamUseCase
from ..core.use_cases.sync_journal_snapshot import SyncJournalSnapshotUseCase


@dataclass(frozen=True, slots=True)
class Container:
    """Dependency injection container graph holding singleton use cases."""

    get_watcher_status_use_case: GetWatcherStatusUseCase
    process_telemetry_stream_use_case: ProcessTelemetryStreamUseCase
    sync_journal_snapshot_use_case: SyncJournalSnapshotUseCase


def build_container(
    journal_dir: Path | None = None,
    poll_interval: float | None = None,
) -> Container:
    """Instantiate concrete driven adapters and wire them into stateless use cases."""
    watcher = FileSystemWatcher(journal_dir=journal_dir, poll_interval=poll_interval)
    egress = NullTransmitter()

    get_status = GetWatcherStatusUseCase(watcher=watcher)
    process_stream = ProcessTelemetryStreamUseCase(watcher=watcher, egress=egress)
    sync_snapshot = SyncJournalSnapshotUseCase(watcher=watcher, egress=egress)

    return Container(
        get_watcher_status_use_case=get_status,
        process_telemetry_stream_use_case=process_stream,
        sync_journal_snapshot_use_case=sync_snapshot,
    )
