"""Composition root wiring adapters and interactors into executable runtime services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..adapters.driven.egress.buffered_queue import BufferedQueueAdapter
from ..adapters.driven.watcher.watcher import FileSystemWatcher
from ..adapters.driving.cli.main import CliTelemetryAdapter
from ..core.use_cases.find_journal_path import FindJournalPathUseCase
from ..core.use_cases.get_auxiliary_snapshot import GetAuxiliarySnapshotUseCase
from ..core.use_cases.get_journal_files import GetJournalFilesUseCase
from ..core.use_cases.get_latest_game_status import GetLatestGameStatusUseCase
from ..core.use_cases.get_telemetry_events import GetTelemetryEventsUseCase
from ..core.use_cases.get_watcher_status import GetWatcherStatusUseCase
from ..core.use_cases.process_telemetry_stream import ProcessTelemetryStreamUseCase
from ..core.use_cases.submit_snapshot_refresh import SubmitSnapshotRefreshUseCase
from ..core.use_cases.sync_journal_snapshot import SyncJournalSnapshotUseCase


@dataclass(frozen=True, slots=True)
class Container:
    """Dependency injection container graph holding singleton use cases and driving adapters."""

    get_watcher_status_use_case: GetWatcherStatusUseCase
    process_telemetry_stream_use_case: ProcessTelemetryStreamUseCase
    sync_journal_snapshot_use_case: SyncJournalSnapshotUseCase
    find_journal_path_use_case: FindJournalPathUseCase
    get_journal_files_use_case: GetJournalFilesUseCase
    get_latest_game_status_use_case: GetLatestGameStatusUseCase
    get_auxiliary_snapshot_use_case: GetAuxiliarySnapshotUseCase
    submit_snapshot_refresh_use_case: SubmitSnapshotRefreshUseCase
    get_telemetry_events_use_case: GetTelemetryEventsUseCase
    cli_adapter: CliTelemetryAdapter


def build_container(
    journal_dir: Path | None = None,
    poll_interval: float | None = None,
    buffer_capacity: int = 10000,
) -> Container:
    """Instantiate concrete driven adapters, wire use cases, and instantiate driving adapters."""
    watcher = FileSystemWatcher(journal_dir=journal_dir, poll_interval=poll_interval)
    egress_buffer = BufferedQueueAdapter(maxsize=buffer_capacity)

    get_status = GetWatcherStatusUseCase(watcher=watcher)
    process_stream = ProcessTelemetryStreamUseCase(watcher=watcher, egress=egress_buffer)
    sync_snapshot = SyncJournalSnapshotUseCase(watcher=watcher, egress=egress_buffer)
    find_path = FindJournalPathUseCase(watcher=watcher)
    get_journals = GetJournalFilesUseCase(watcher=watcher)
    get_game_status = GetLatestGameStatusUseCase(watcher=watcher)
    get_aux = GetAuxiliarySnapshotUseCase(watcher=watcher)
    submit_refresh = SubmitSnapshotRefreshUseCase(watcher=watcher)
    get_events = GetTelemetryEventsUseCase(queue=egress_buffer)

    cli_adapter = CliTelemetryAdapter(watcher_status_port=get_status)

    return Container(
        get_watcher_status_use_case=get_status,
        process_telemetry_stream_use_case=process_stream,
        sync_journal_snapshot_use_case=sync_snapshot,
        find_journal_path_use_case=find_path,
        get_journal_files_use_case=get_journals,
        get_latest_game_status_use_case=get_game_status,
        get_auxiliary_snapshot_use_case=get_aux,
        submit_snapshot_refresh_use_case=submit_refresh,
        get_telemetry_events_use_case=get_events,
        cli_adapter=cli_adapter,
    )


def main() -> int:
    """CLI execution entrypoint wired from composition root."""
    container = build_container()
    code, payload = container.cli_adapter.run()
    print(f"ed-telemetry baseline verified: status retrieved (active={payload['is_active']})")
    return code
