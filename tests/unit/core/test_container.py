"""Unit tests for bootstrap container wiring and CLI adapter."""

from __future__ import annotations

from ed_telemetry.adapters.driving.api.server import HttpApiAdapter
from ed_telemetry.bootstrap.container import Container, build_container
from ed_telemetry.core.use_cases.find_journal_path import FindJournalPathUseCase
from ed_telemetry.core.use_cases.find_telemetry_events import FindTelemetryEventsUseCase
from ed_telemetry.core.use_cases.get_auxiliary_snapshot import GetAuxiliarySnapshotUseCase
from ed_telemetry.core.use_cases.get_journal_files import GetJournalFilesUseCase
from ed_telemetry.core.use_cases.get_latest_game_status import GetLatestGameStatusUseCase
from ed_telemetry.core.use_cases.get_telemetry_events import GetTelemetryEventsUseCase
from ed_telemetry.core.use_cases.get_telemetry_stream import GetTelemetryStreamUseCase
from ed_telemetry.core.use_cases.get_watcher_status import GetWatcherStatusUseCase
from ed_telemetry.core.use_cases.process_telemetry_stream import (
    ProcessTelemetryStreamUseCase,
)
from ed_telemetry.core.use_cases.submit_snapshot_refresh import SubmitSnapshotRefreshUseCase
from ed_telemetry.core.use_cases.sync_journal_snapshot import (
    SyncJournalSnapshotUseCase,
)


class TestContainer:
    """Verifies build_container returns properly configured Container."""

    def test_build_container_constructs_graph(self) -> None:
        container = build_container()

        assert isinstance(container, Container)
        assert isinstance(container.get_watcher_status_use_case, GetWatcherStatusUseCase)
        assert isinstance(
            container.process_telemetry_stream_use_case,
            ProcessTelemetryStreamUseCase,
        )
        assert isinstance(
            container.sync_journal_snapshot_use_case,
            SyncJournalSnapshotUseCase,
        )
        assert isinstance(
            container.find_journal_path_use_case,
            FindJournalPathUseCase,
        )
        assert isinstance(
            container.get_journal_files_use_case,
            GetJournalFilesUseCase,
        )
        assert isinstance(
            container.get_latest_game_status_use_case,
            GetLatestGameStatusUseCase,
        )
        assert isinstance(
            container.get_auxiliary_snapshot_use_case,
            GetAuxiliarySnapshotUseCase,
        )
        assert isinstance(
            container.submit_snapshot_refresh_use_case,
            SubmitSnapshotRefreshUseCase,
        )
        assert isinstance(
            container.get_telemetry_events_use_case,
            GetTelemetryEventsUseCase,
        )
        assert isinstance(
            container.find_telemetry_events_use_case,
            FindTelemetryEventsUseCase,
        )
        assert isinstance(
            container.get_telemetry_stream_use_case,
            GetTelemetryStreamUseCase,
        )
        assert isinstance(
            container.http_api_adapter,
            HttpApiAdapter,
        )
