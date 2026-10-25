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

    def test_audit_handler_transforms_and_forwards_to_egress(self) -> None:
        from ed_telemetry.core.ports.dto.telemetry_dto import WatcherAuditEventDTO

        watcher = FakeWatcherAdapter()
        egress = FakeEgressAdapter()
        _use_case = ProcessTelemetryStreamUseCase(watcher=watcher, egress=egress)

        now = datetime.now(UTC)
        audit_event = WatcherAuditEventDTO(
            timestamp=now,
            action="file_rotation",
            target_path="/tmp/journal.log",
            detail="Rotated to new segment",
        )

        watcher.emit_test_audit(audit_event)

        assert len(egress.sent_payloads) == 1
        payload = egress.sent_payloads[0]
        assert payload.topic == "telemetry.audit"
        assert payload.timestamp == now
        assert b"file_rotation" in payload.payload_bytes
        assert b"Rotated to new segment" in payload.payload_bytes
        assert ("action", "file_rotation") in payload.metadata


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


class TestFindJournalPathUseCase:
    """Verifies FindJournalPathUseCase."""

    def test_find_path_returns_dto(self) -> None:
        from ed_telemetry.core.use_cases.find_journal_path import FindJournalPathUseCase

        watcher = FakeWatcherAdapter(journal_dir="/custom/games/ed")
        use_case = FindJournalPathUseCase(watcher=watcher)

        res = use_case.find_path()
        assert res.resolved_path == "/custom/games/ed"
        assert res.platform == "linux"
        assert res.discovery_source == "fake_test_double"


class TestGetJournalFilesUseCase:
    """Verifies GetJournalFilesUseCase."""

    def test_get_journals_returns_candidates(self) -> None:
        from ed_telemetry.core.use_cases.get_journal_files import GetJournalFilesUseCase

        watcher = FakeWatcherAdapter(journal_dir="/custom/games/ed")
        use_case = GetJournalFilesUseCase(watcher=watcher)

        res = use_case.get_journals()
        assert res.journal_dir == "/custom/games/ed"
        assert len(res.candidates) == 1
        assert res.active_journal == "Journal.2026-10-25T000000.01.log"


class TestGetLatestGameStatusUseCase:
    """Verifies GetLatestGameStatusUseCase."""

    def test_get_game_status_returns_snapshot(self) -> None:
        from ed_telemetry.core.use_cases.get_latest_game_status import GetLatestGameStatusUseCase

        watcher = FakeWatcherAdapter(journal_dir="/custom/games/ed")
        use_case = GetLatestGameStatusUseCase(watcher=watcher)

        status = use_case.get_game_status()
        assert status.exists is True
        assert b"Flags" in status.raw_payload


class TestGetAuxiliarySnapshotUseCase:
    """Verifies GetAuxiliarySnapshotUseCase."""

    def test_get_snapshot_returns_target_payload(self) -> None:
        from ed_telemetry.core.use_cases.get_auxiliary_snapshot import GetAuxiliarySnapshotUseCase

        watcher = FakeWatcherAdapter(journal_dir="/custom/games/ed")
        use_case = GetAuxiliarySnapshotUseCase(watcher=watcher)

        snapshot = use_case.get_snapshot("NavRoute.json")
        assert snapshot.exists is True
        assert snapshot.target_name == "NavRoute.json"
        assert b"NavRoute" in snapshot.raw_payload


class TestSubmitSnapshotRefreshUseCase:
    """Verifies SubmitSnapshotRefreshUseCase."""

    def test_refresh_snapshot_submits_hint(self) -> None:
        from ed_telemetry.core.use_cases.submit_snapshot_refresh import SubmitSnapshotRefreshUseCase

        watcher = FakeWatcherAdapter(journal_dir="/custom/games/ed")
        use_case = SubmitSnapshotRefreshUseCase(watcher=watcher)

        res = use_case.refresh_snapshot("Market.json")
        assert res.accepted is True
        assert res.target_name == "Market.json"
        assert res.action == "hint_snapshot"


class TestGetTelemetryEventsUseCase:
    """Verifies GetTelemetryEventsUseCase consuming from EventQueuePort."""

    def test_get_events_drains_events_from_queue(self) -> None:
        from datetime import UTC, datetime

        from ed_telemetry.core.ports.dto import TelemetryPayloadDTO
        from ed_telemetry.core.use_cases.get_telemetry_events import GetTelemetryEventsUseCase
        from tests.doubles.fake_adapters import FakeEventQueueAdapter

        ev1 = TelemetryPayloadDTO(
            topic="telemetry.journal",
            timestamp=datetime.now(UTC),
            payload_bytes=b'{"event":"FSDJump"}',
        )
        ev2 = TelemetryPayloadDTO(
            topic="telemetry.status",
            timestamp=datetime.now(UTC),
            payload_bytes=b'{"Flags":16}',
        )
        queue = FakeEventQueueAdapter(initial_events=[ev1, ev2])
        use_case = GetTelemetryEventsUseCase(queue=queue)

        batch = use_case.get_events(limit=10)
        assert len(batch.events) == 2
        assert batch.events[0].topic == "telemetry.journal"
        assert batch.events[1].topic == "telemetry.status"
        assert batch.remaining_count == 0
        assert batch.dropped_count == 0

    def test_get_events_respects_batch_limit(self) -> None:
        from datetime import UTC, datetime

        from ed_telemetry.core.ports.dto import TelemetryPayloadDTO
        from ed_telemetry.core.use_cases.get_telemetry_events import GetTelemetryEventsUseCase
        from tests.doubles.fake_adapters import FakeEventQueueAdapter

        events = [
            TelemetryPayloadDTO(topic=f"telemetry.event_{i}", timestamp=datetime.now(UTC), payload_bytes=b"{}")
            for i in range(5)
        ]
        queue = FakeEventQueueAdapter(initial_events=events)
        use_case = GetTelemetryEventsUseCase(queue=queue)

        batch1 = use_case.get_events(limit=2)
        assert len(batch1.events) == 2
        assert batch1.remaining_count == 3

        batch2 = use_case.get_events(limit=10)
        assert len(batch2.events) == 3
        assert batch2.remaining_count == 0


class TestFindTelemetryEventsUseCase:
    """Verifies FindTelemetryEventsUseCase querying TelemetryRepositoryPort."""

    def test_find_events_delegates_to_repository(self) -> None:
        from datetime import UTC, datetime

        from ed_telemetry.core.ports.dto import TelemetryPayloadDTO, TelemetryQueryDTO
        from ed_telemetry.core.use_cases.find_telemetry_events import FindTelemetryEventsUseCase
        from tests.doubles.fake_adapters import FakeTelemetryRepositoryAdapter

        repo = FakeTelemetryRepositoryAdapter()
        repo.insert_event(
            TelemetryPayloadDTO(
                topic="telemetry.journal",
                timestamp=datetime.now(UTC),
                payload_bytes=b"{}",
            )
        )
        repo.insert_event(
            TelemetryPayloadDTO(
                topic="telemetry.status",
                timestamp=datetime.now(UTC),
                payload_bytes=b"{}",
            )
        )

        use_case = FindTelemetryEventsUseCase(repository=repo)
        results = use_case.find_events(TelemetryQueryDTO(topic="telemetry.journal"))
        assert len(results) == 1
        assert results[0].topic == "telemetry.journal"


class TestGetTelemetryStreamUseCase:
    """Verifies GetTelemetryStreamUseCase streaming from EventQueuePort."""

    def test_stream_events_yields_payloads(self) -> None:
        from datetime import UTC, datetime

        from ed_telemetry.core.ports.dto import TelemetryPayloadDTO
        from ed_telemetry.core.use_cases.get_telemetry_stream import GetTelemetryStreamUseCase
        from tests.doubles.fake_adapters import FakeEventQueueAdapter

        ev = TelemetryPayloadDTO(
            topic="telemetry.journal",
            timestamp=datetime.now(UTC),
            payload_bytes=b'{"event":"Docked"}',
        )
        queue = FakeEventQueueAdapter(initial_events=[ev])
        use_case = GetTelemetryStreamUseCase(queue=queue)

        gen = use_case.stream_events(timeout=0.01)
        yielded = next(gen)
        assert yielded.topic == "telemetry.journal"
        assert yielded.payload_bytes == b'{"event":"Docked"}'
