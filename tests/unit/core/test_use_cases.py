"""Unit tests for core telemetry use cases using in-memory test doubles."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ed_telemetry.core.ports.dto.telemetry_dto import (
    FileIngestionEventDTO,
    StartMonitoringDTO,
)
from ed_telemetry.core.use_cases.get_watcher_status import GetWatcherStatusUseCase
from ed_telemetry.core.use_cases.process_telemetry_stream import (
    ProcessTelemetryStreamUseCase,
)
from ed_telemetry.core.use_cases.sync_journal_snapshot import (
    SyncJournalSnapshotUseCase,
)
from tests.doubles.fake_adapters import FakeEgressAdapter, FakeWatcherAdapter


class TestGetWatcherStatusUseCase:
    """Verifies GetWatcherStatusUseCase queries watcher port."""

    def test_returns_inactive_status_initially(self) -> None:
        watcher = FakeWatcherAdapter(journal_dir="/tmp/journals")
        use_case = GetWatcherStatusUseCase(watcher=watcher)

        status = use_case.get_status()

        assert not status.is_active
        assert status.monitored_directory == "/tmp/journals"
        assert status.active_journal is None

    def test_returns_active_status_when_running(self) -> None:
        watcher = FakeWatcherAdapter(journal_dir="/tmp/journals")
        watcher.start()
        use_case = GetWatcherStatusUseCase(watcher=watcher)

        status = use_case.get_status()

        assert status.is_active
        assert status.monitored_directory == "/tmp/journals"


class TestProcessTelemetryStreamUseCase:
    """Verifies ProcessTelemetryStreamUseCase starts/stops stream and routes events."""

    def test_lifecycle_delegates_to_watcher(self) -> None:
        watcher = FakeWatcherAdapter()
        egress = FakeEgressAdapter()
        use_case = ProcessTelemetryStreamUseCase(watcher=watcher, egress=egress)

        assert not watcher.is_active

        use_case.start_streaming(StartMonitoringDTO())
        assert watcher.is_active

        use_case.stop_streaming()
        assert not watcher.is_active

    def test_event_handler_transforms_and_forwards_to_egress(self) -> None:
        watcher = FakeWatcherAdapter()
        egress = FakeEgressAdapter()
        _use_case = ProcessTelemetryStreamUseCase(watcher=watcher, egress=egress)

        now = datetime.now(UTC)
        event = FileIngestionEventDTO(
            event_id=uuid4(),
            timestamp=now,
            file_kind="journal",
            target_path="/tmp/journal.log",
            raw_payload=b'{"event":"Docked"}',
            start_offset=0,
            end_offset=18,
            line_number=1,
            part=None,
            raw_hash="hash123",
        )

        watcher.emit_test_event(event)

        assert len(egress.sent_payloads) == 1
        payload = egress.sent_payloads[0]
        assert payload.topic == "telemetry.journal"
        assert payload.payload_bytes == b'{"event":"Docked"}'
        assert payload.timestamp == now


class TestSyncJournalSnapshotUseCase:
    """Verifies SyncJournalSnapshotUseCase executes snapshot sync."""

    def test_sync_snapshots_returns_result(self) -> None:
        watcher = FakeWatcherAdapter(journal_dir="/tmp/journals")
        egress = FakeEgressAdapter()
        use_case = SyncJournalSnapshotUseCase(watcher=watcher, egress=egress)

        result = use_case.sync_snapshots()

        assert result.files_inspected == 0
        assert result.payloads_emitted == 0
        assert result.active_journal_file is None
