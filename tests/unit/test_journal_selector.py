"""Unit tests for JournalSelector and journal candidate sorting strategy (ADR 0006 / SDD-004)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from infrastructure.watcher.exceptions import JournalDirectoryAccessError
from infrastructure.watcher.selector import (
    JournalCandidate,
    JournalSelector,
    StreamPosition,
    parse_journal_timestamp,
)


class TestJournalTimestampParsing:
    """Test parsing of FDev timestamp schemas."""

    def test_parses_odyssey_iso_timestamp(self) -> None:
        raw = "2026-10-08T123045"
        dt = parse_journal_timestamp(raw)
        assert dt == datetime(2026, 10, 8, 12, 30, 45, tzinfo=UTC)

    def test_parses_legacy_compact_timestamp(self) -> None:
        raw = "261008123045"
        dt = parse_journal_timestamp(raw)
        assert dt == datetime(2026, 10, 8, 12, 30, 45, tzinfo=UTC)

    def test_rejects_invalid_timestamp_formats(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized journal timestamp format"):
            parse_journal_timestamp("invalid-date")
        with pytest.raises(ValueError, match="Unrecognized journal timestamp format"):
            parse_journal_timestamp("2026-10-08")


class TestJournalCandidateComparison:
    """Test rich comparison operators honoring the composite sort key (timestamp, part, mtime)."""

    def test_higher_timestamp_ranks_higher(self, tmp_path: Path) -> None:
        p1 = tmp_path / "Journal.2026-10-08T100000.01.log"
        p2 = tmp_path / "Journal.2026-10-08T110000.01.log"
        p1.touch()
        p2.touch()

        c1 = JournalCandidate(
            path=p1,
            filename=p1.name,
            build=None,
            timestamp=datetime(2026, 10, 8, 10, 0, tzinfo=UTC),
            part=1,
            mtime=100.0,
            is_standard_format=True,
            sort_key=(datetime(2026, 10, 8, 10, 0, tzinfo=UTC), 1, 100.0),
        )
        c2 = JournalCandidate(
            path=p2,
            filename=p2.name,
            build=None,
            timestamp=datetime(2026, 10, 8, 11, 0, tzinfo=UTC),
            part=1,
            mtime=100.0,
            is_standard_format=True,
            sort_key=(datetime(2026, 10, 8, 11, 0, tzinfo=UTC), 1, 100.0),
        )

        assert c1 < c2
        assert c2 > c1
        assert max([c1, c2]) == c2

    def test_higher_part_number_ranks_higher_when_timestamps_match(self, tmp_path: Path) -> None:
        p1 = tmp_path / "Journal.2026-10-08T100000.01.log"
        p2 = tmp_path / "Journal.2026-10-08T100000.02.log"
        p1.touch()
        p2.touch()

        ts = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)
        c1 = JournalCandidate(
            path=p1,
            filename=p1.name,
            build=None,
            timestamp=ts,
            part=1,
            mtime=100.0,
            is_standard_format=True,
            sort_key=(ts, 1, 100.0),
        )
        c2 = JournalCandidate(
            path=p2,
            filename=p2.name,
            build=None,
            timestamp=ts,
            part=2,
            mtime=100.0,
            is_standard_format=True,
            sort_key=(ts, 2, 100.0),
        )

        assert c1 < c2
        assert c2 > c1
        assert max([c1, c2]) == c2

    def test_mtime_tiebreaker_when_timestamp_and_part_match(self, tmp_path: Path) -> None:
        p1 = tmp_path / "Journal.file1.log"
        p2 = tmp_path / "Journal.file2.log"
        p1.touch()
        p2.touch()

        min_ts = datetime.min.replace(tzinfo=UTC)
        c1 = JournalCandidate(
            path=p1,
            filename=p1.name,
            build=None,
            timestamp=min_ts,
            part=0,
            mtime=100.0,
            is_standard_format=False,
            sort_key=(min_ts, 0, 100.0),
        )
        c2 = JournalCandidate(
            path=p2,
            filename=p2.name,
            build=None,
            timestamp=min_ts,
            part=0,
            mtime=200.0,
            is_standard_format=False,
            sort_key=(min_ts, 0, 200.0),
        )

        assert c1 < c2
        assert c2 > c1


class TestJournalSelector:
    """Test candidate enumeration, active journal resolution, and successor detection."""

    def test_empty_directory_returns_none_and_empty_sequence(self, tmp_path: Path) -> None:
        selector = JournalSelector(tmp_path)
        assert selector.find_candidates() == ()
        assert selector.get_active_journal() is None

    def test_inaccessible_or_missing_directory_raises_error(self, tmp_path: Path) -> None:
        missing_dir = tmp_path / "non_existent_dir"
        selector = JournalSelector(missing_dir)

        with pytest.raises(JournalDirectoryAccessError) as exc_info:
            selector.find_candidates()
        assert exc_info.value.reason == "does_not_exist"

        file_as_dir = tmp_path / "not_a_dir.txt"
        file_as_dir.touch()
        selector_file = JournalSelector(file_as_dir)
        with pytest.raises(JournalDirectoryAccessError) as exc_info:
            selector_file.find_candidates()
        assert exc_info.value.reason == "not_a_directory"

    def test_filters_out_non_matching_files(self, tmp_path: Path) -> None:
        (tmp_path / "Status.json").touch()
        (tmp_path / "Market.json").touch()
        (tmp_path / "Journal.txt").touch()
        (tmp_path / "Cargo.json").touch()
        (tmp_path / "Journal.2026-10-08T120000.01.log").touch()

        selector = JournalSelector(tmp_path)
        candidates = selector.find_candidates()

        assert len(candidates) == 1
        assert candidates[0].filename == "Journal.2026-10-08T120000.01.log"

    def test_selects_active_journal_across_odyssey_legacy_and_beta(self, tmp_path: Path) -> None:
        f_legacy = tmp_path / "Journal.220101120000.01.log"  # 2022-01-01
        f_beta = tmp_path / "JournalBeta.2026-05-01T120000.01.log"  # 2026-05-01 Beta
        f_ody1 = tmp_path / "Journal.2026-10-08T120000.01.log"  # 2026-10-08 12:00:00 Part 01
        f_ody2 = tmp_path / "Journal.2026-10-08T120000.02.log"  # 2026-10-08 12:00:00 Part 02

        f_legacy.touch()
        f_beta.touch()
        f_ody1.touch()
        f_ody2.touch()

        selector = JournalSelector(tmp_path)
        candidates = selector.find_candidates()

        assert len(candidates) == 4
        assert [c.filename for c in candidates] == [
            "Journal.220101120000.01.log",
            "JournalBeta.2026-05-01T120000.01.log",
            "Journal.2026-10-08T120000.01.log",
            "Journal.2026-10-08T120000.02.log",
        ]

        active = selector.get_active_journal()
        assert active is not None
        assert active.filename == "Journal.2026-10-08T120000.02.log"
        assert active.part == 2
        assert active.build is None

    def test_get_successor_detects_part_rollover_and_new_session(self, tmp_path: Path) -> None:
        p1 = tmp_path / "Journal.2026-10-08T120000.01.log"
        p1.touch()

        selector = JournalSelector(tmp_path)
        current = selector.get_active_journal()
        assert current is not None
        assert current.filename == "Journal.2026-10-08T120000.01.log"

        # No successor initially
        assert selector.get_successor(current) is None

        # Simulate game spawning part 02
        p2 = tmp_path / "Journal.2026-10-08T120000.02.log"
        p2.touch()

        successor = selector.get_successor(current)
        assert successor is not None
        assert successor.filename == "Journal.2026-10-08T120000.02.log"
        assert successor.part == 2

        # Simulate game spawning a new session next day
        p3 = tmp_path / "Journal.2026-10-09T080000.01.log"
        p3.touch()

        new_session = selector.get_successor(successor)
        assert new_session is not None
        assert new_session.filename == "Journal.2026-10-09T080000.01.log"
        assert new_session.part == 1

    def test_stream_position_enum_values(self) -> None:
        assert StreamPosition.HEAD == "head"
        assert StreamPosition.TAIL == "tail"
        assert StreamPosition.LOCATE_EVENT == "locate_event"
