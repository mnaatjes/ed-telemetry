"""Active journal candidate selection, sorting, and continuous succession."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from ed_watcher.exceptions import JournalDirectoryAccessError

# Canonical Journal filename regex adhering to FDev Odyssey, Legacy, and Pre-Release conventions.
JOURNAL_FILE_REGEX = re.compile(
    r"^Journal(?P<build>Alpha|Beta)?"
    r"\.(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{6}|\d{12})"
    r"\.(?P<part>\d{2})"
    r"\.log$",
    re.IGNORECASE,
)


class StreamPosition(StrEnum):
    """Declarative startup positioning parameter for journal streaming."""

    HEAD = "head"  # Read from byte offset 0 (full historical replay)
    TAIL = "tail"  # Read from current EOF (live monitoring only)
    LOCATE_EVENT = "locate_event"  # Fast scan backwards from EOF for state anchors


@dataclass(frozen=True)
class JournalCandidate:
    """
    Immutable, comparable representation of an evaluated journal file candidate.
    Ordering strictly honors composite sort key: (timestamp, part, mtime).
    """

    path: Path
    filename: str
    build: str | None
    timestamp: datetime
    part: int
    mtime: float
    is_standard_format: bool
    sort_key: tuple[datetime, int, float] = field(compare=True, repr=False)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, JournalCandidate):
            return NotImplemented
        return self.sort_key < other.sort_key

    def __le__(self, other: object) -> bool:
        if not isinstance(other, JournalCandidate):
            return NotImplemented
        return self.sort_key <= other.sort_key

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, JournalCandidate):
            return NotImplemented
        return self.sort_key > other.sort_key

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, JournalCandidate):
            return NotImplemented
        return self.sort_key >= other.sort_key


def parse_journal_timestamp(ts_str: str) -> datetime:
    """
    Parse ISO-like (Odyssey) or compact (Legacy) journal timestamp strings into UTC datetime.

    Supported formats:
    - Odyssey: YYYY-MM-DDTHHMMSS (e.g., '2026-10-08T120000')
    - Legacy:  YYMMDDHHMMSS      (e.g., '261008120000')
    """
    try:
        if len(ts_str) == 17 and ts_str[10] == "T":
            # Odyssey format: YYYY-MM-DDTHHMMSS
            return datetime.strptime(ts_str, "%Y-%m-%dT%H%M%S").replace(tzinfo=UTC)
        if len(ts_str) == 12:
            # Legacy compact format: YYMMDDHHMMSS
            return datetime.strptime(ts_str, "%y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError as err:
        raise ValueError(f"Unrecognized journal timestamp format: '{ts_str}'") from err
    raise ValueError(f"Unrecognized journal timestamp format: '{ts_str}'")


class JournalSelector:
    """
    Stateless evaluator responsible for discovering, filtering, sorting,
    and selecting active and successor journal file candidates.
    """

    def __init__(self, journal_dir: Path) -> None:
        self.journal_dir = journal_dir

    def _validate_directory(self) -> None:
        """Validate that target path exists, is a directory, and has read permissions."""
        if not self.journal_dir.exists():
            raise JournalDirectoryAccessError(self.journal_dir, reason="does_not_exist")
        if not self.journal_dir.is_dir():
            raise JournalDirectoryAccessError(self.journal_dir, reason="not_a_directory")

    def evaluate_candidate(self, filepath: Path) -> JournalCandidate:
        """
        Evaluate a single filesystem entry into a JournalCandidate.
        Falls back to (datetime.min, 0, mtime) if filename parsing fails.
        """
        try:
            mtime = filepath.stat().st_mtime
        except OSError:
            mtime = 0.0

        match = JOURNAL_FILE_REGEX.match(filepath.name)
        if match:
            build = match.group("build")
            ts_raw = match.group("timestamp")
            part_raw = match.group("part")
            try:
                ts = parse_journal_timestamp(ts_raw)
                part = int(part_raw)
                sort_key = (ts, part, mtime)
                return JournalCandidate(
                    path=filepath,
                    filename=filepath.name,
                    build=build,
                    timestamp=ts,
                    part=part,
                    mtime=mtime,
                    is_standard_format=True,
                    sort_key=sort_key,
                )
            except (ValueError, OverflowError):
                pass

        # Non-standard or unparseable fallback
        min_ts = datetime.min.replace(tzinfo=UTC)
        sort_key = (min_ts, 0, mtime)
        return JournalCandidate(
            path=filepath,
            filename=filepath.name,
            build=None,
            timestamp=min_ts,
            part=0,
            mtime=mtime,
            is_standard_format=False,
            sort_key=sort_key,
        )

    def find_candidates(self) -> Sequence[JournalCandidate]:
        """
        Scan directory and return all matching candidates sorted monotonically ascending.
        Raises JournalDirectoryAccessError if directory cannot be read.
        """
        self._validate_directory()

        candidates: list[JournalCandidate] = []
        try:
            with os.scandir(self.journal_dir) as entries:
                for entry in entries:
                    if entry.is_file():
                        # Only consider files matching candidate pattern or Journal prefix
                        if JOURNAL_FILE_REGEX.match(entry.name):
                            candidates.append(self.evaluate_candidate(Path(entry.path)))
        except PermissionError as err:
            raise JournalDirectoryAccessError(self.journal_dir, reason="permission_denied") from err
        except OSError as err:
            raise JournalDirectoryAccessError(self.journal_dir, reason="os_error") from err

        candidates.sort()
        return tuple(candidates)

    def get_active_journal(self) -> JournalCandidate | None:
        """
        Return the highest-ranking candidate, or None if the directory is empty of journal files.
        Non-fatal waiting condition per ADR 0006 Section 4.1.
        """
        candidates = self.find_candidates()
        if not candidates:
            return None
        return max(candidates)

    def get_successor(self, current: JournalCandidate) -> JournalCandidate | None:
        """
        Evaluate if a strictly newer candidate exists relative to the currently tailed file.
        Returns the newest successor candidate if one ranks higher, else None.
        """
        active = self.get_active_journal()
        if active is None:
            return None
        if active > current:
            return active
        return None
