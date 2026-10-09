"""Status and auxiliary snapshot identification subsystem."""

from ed_watcher.snapshots.identifier import SnapshotIdentifier
from ed_watcher.snapshots.models import SnapshotCandidate
from ed_watcher.snapshots.registry import (
    CANONICAL_AUXILIARY_SNAPSHOTS,
    CANONICAL_STATUS_FILE,
    SnapshotRegistry,
)

__all__ = [
    "CANONICAL_AUXILIARY_SNAPSHOTS",
    "CANONICAL_STATUS_FILE",
    "SnapshotCandidate",
    "SnapshotIdentifier",
    "SnapshotRegistry",
]
