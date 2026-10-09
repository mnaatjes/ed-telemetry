"""Data models for status and auxiliary snapshot candidates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnapshotCandidate:
    """
    Immutable representation of an identified snapshot file candidate on disk.
    """

    canonical_name: str
    resolved_path: Path
    exists: bool
    is_canonical_casing: bool
    mtime: float
    size: int
