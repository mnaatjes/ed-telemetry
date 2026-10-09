"""Unit tests for the File Ingestion Engine and Reactive Reactor (ADR 0008 / SDD-006)."""

import time
from pathlib import Path

from ed_watcher.engine import (
    FileIngestionEvent,
    FileKind,
    JournalStreamContext,
    JournalTailer,
    SnapshotFreshnessTracker,
    SnapshotReader,
    WatcherAuditAction,
    WatcherAuditEvent,
    WatcherHintAction,
    WatcherIngestCommand,
    WatcherReactor,
)
from ed_watcher.selector import StreamPosition


class TestSnapshotFreshnessTracker:
    """Test 64-bit BLAKE2b deduplication tracker."""

    def test_deduplicates_identical_payloads(self) -> None:
        tracker = SnapshotFreshnessTracker()
        payload = b'{"event": "Status", "Flags": 16}'

        is_fresh, hash1 = tracker.check_and_update("Status.json", payload)
        assert is_fresh is True
        assert len(hash1) == 16  # 64-bit hex digest is 16 characters

        # Repeat identical payload
        is_fresh2, hash2 = tracker.check_and_update("Status.json", payload)
        assert is_fresh2 is False
        assert hash2 == hash1

        # Changed payload
        new_payload = b'{"event": "Status", "Flags": 32}'
        is_fresh3, hash3 = tracker.check_and_update("Status.json", new_payload)
        assert is_fresh3 is True
        assert hash3 != hash1


class TestJournalStreamContextAndTailer:
    """Test monotonic forward seek, newline boundary verification, and fragment circuit breaker."""

    def test_monotonic_forward_seek_emits_lines_and_advances_offset(self, tmp_path: Path) -> None:
        journal_path = tmp_path / "Journal.2026-10-09T120000.01.log"
        journal_path.write_bytes(b'{"event":"FileHeader"}\n{"event":"LoadGame"}\n')

        context = JournalStreamContext.open(journal_path, part=1, position=StreamPosition.HEAD)
        assert context.last_valid_offset == 0

        tailer = JournalTailer()
        data_events, audit_events = tailer.step(context)

        assert len(data_events) == 2
        assert len(audit_events) == 0
        assert data_events[0].line_number == 1
        assert data_events[0].start_offset == 0
        assert data_events[0].raw_payload == b'{"event":"FileHeader"}\n'
        assert data_events[1].line_number == 2
        assert context.last_valid_offset == len(b'{"event":"FileHeader"}\n{"event":"LoadGame"}\n')

        context.close()

    def test_incomplete_line_held_in_accumulator_until_newline_flushed(self, tmp_path: Path) -> None:
        journal_path = tmp_path / "Journal.2026-10-09T120000.01.log"
        # Half a line flushed
        journal_path.write_bytes(b'{"event":"PartialEvent"')

        context = JournalStreamContext.open(journal_path, part=1, position=StreamPosition.HEAD)
        tailer = JournalTailer()

        # First read: incomplete fragment
        data_events, audit_events = tailer.step(context)
        assert len(data_events) == 0
        assert context.last_valid_offset == 0
        assert context.fragment_accumulator == bytearray(b'{"event":"PartialEvent"')

        # Game flushes the rest of the line with newline
        with journal_path.open("ab") as f:
            f.write(b', "Val": 1}\n')

        # Second read: completes the line
        data_events2, audit_events2 = tailer.step(context)
        assert len(data_events2) == 1
        assert data_events2[0].raw_payload == b'{"event":"PartialEvent", "Val": 1}\n'
        assert context.last_valid_offset == len(b'{"event":"PartialEvent", "Val": 1}\n')
        assert len(context.fragment_accumulator) == 0

        context.close()

    def test_fragment_stagnant_circuit_breaker_trips_and_skips(self, tmp_path: Path) -> None:
        journal_path = tmp_path / "Journal.2026-10-09T120000.01.log"
        journal_path.write_bytes(b"BrokenCorruptedFragmentWithoutNewline")

        context = JournalStreamContext.open(journal_path, part=1, position=StreamPosition.HEAD)
        # Configure tight timeout of 0.05 seconds for test
        tailer = JournalTailer(stagnant_timeout=0.05)

        # Initial read buffers the fragment
        tailer.step(context)
        assert len(context.fragment_accumulator) > 0

        # Wait for stagnant timeout to expire
        time.sleep(0.06)

        # Step again: circuit breaker must trip
        data_events, audit_events = tailer.step(context)
        assert len(data_events) == 0
        assert len(audit_events) == 1
        assert audit_events[0].action == WatcherAuditAction.LINE_QUARANTINED
        assert len(context.fragment_accumulator) == 0
        assert context.last_valid_offset == len(b"BrokenCorruptedFragmentWithoutNewline")

        context.close()


class TestSnapshotReader:
    """Test atomic reading and structural boundary guards."""

    def test_reads_valid_snapshot(self, tmp_path: Path) -> None:
        status_path = tmp_path / "Status.json"
        status_path.write_bytes(b'{"event": "Status", "Pips": [4, 4, 4]}')

        reader = SnapshotReader()
        event, audits = reader.read_snapshot(status_path, FileKind.STATUS)

        assert event is not None
        assert event.file_kind == FileKind.STATUS
        assert event.raw_payload == b'{"event": "Status", "Pips": [4, 4, 4]}'

        # Read identical again: should return None (deduplicated)
        event2, audits2 = reader.read_snapshot(status_path, FileKind.STATUS)
        assert event2 is None

    def test_rejects_non_bracketed_or_truncated_snapshot(self, tmp_path: Path) -> None:
        market_path = tmp_path / "Market.json"
        market_path.write_bytes(b"TruncatedPayloadMissingBrackets")

        reader = SnapshotReader(retry_backoffs=(0.005,))
        event, audits = reader.read_snapshot(market_path, FileKind.SNAPSHOT)

        assert event is None
        assert any(a.action == WatcherAuditAction.RETRY_BACKOFF for a in audits)


class TestWatcherReactor:
    """Test unified reactor loop, part rollovers, and command queue."""

    def test_reactor_startup_and_step_with_part_rollover(self, tmp_path: Path) -> None:
        emitted_data: list[FileIngestionEvent] = []
        emitted_audits: list[WatcherAuditEvent] = []

        # Create part 01
        p1 = tmp_path / "Journal.2026-10-09T100000.01.log"
        p1.write_bytes(b'{"event":"PartOne"}\n')

        reactor = WatcherReactor(
            journal_dir=tmp_path,
            stream_position=StreamPosition.HEAD,
            data_listener=emitted_data.append,
            audit_listener=emitted_audits.append,
        )

        reactor.start()
        assert reactor.is_running is True

        # Initial step reads part 01
        events1 = reactor.step_once()
        assert len(events1) == 1
        assert events1[0].raw_payload == b'{"event":"PartOne"}\n'

        # Spawn part 02 (rollover)
        p2 = tmp_path / "Journal.2026-10-09T100000.02.log"
        p2.write_bytes(b'{"event":"PartTwo"}\n')

        # Step reactor: must trigger rollover and drain
        events2 = reactor.step_once()
        assert len(events2) == 1
        assert events2[0].raw_payload == b'{"event":"PartTwo"}\n'
        assert events2[0].part == 2

        assert any(a.action == WatcherAuditAction.PART_ROLLOVER for a in emitted_audits)

        reactor.stop()
        assert reactor.is_running is False

    def test_inbound_hint_command_queue(self, tmp_path: Path) -> None:
        emitted_data: list[FileIngestionEvent] = []
        reactor = WatcherReactor(
            journal_dir=tmp_path,
            data_listener=emitted_data.append,
        )
        reactor.start()

        (tmp_path / "Market.json").write_bytes(b'{"event":"Market","Items":[]}')

        # Submit hint across boundary
        success = reactor.submit_hint(
            WatcherIngestCommand(action=WatcherHintAction.HINT_SNAPSHOT, target_name="Market.json")
        )
        assert success is True

        metrics = reactor.get_queue_metrics()
        assert metrics.total_enqueued == 1

        # Step reactor dispatches the hint
        reactor.step_once()
        metrics_after = reactor.get_queue_metrics()
        assert metrics_after.total_processed == 1
        assert len(emitted_data) == 1
        assert emitted_data[0].target_path.name == "Market.json"

        reactor.stop()
