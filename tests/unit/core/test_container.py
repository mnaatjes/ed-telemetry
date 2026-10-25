"""Unit tests for bootstrap container wiring and CLI adapter."""

from __future__ import annotations

from ed_telemetry.bootstrap.container import Container, build_container
from ed_telemetry.core.use_cases.get_watcher_status import GetWatcherStatusUseCase
from ed_telemetry.core.use_cases.process_telemetry_stream import (
    ProcessTelemetryStreamUseCase,
)
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
