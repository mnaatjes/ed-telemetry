"""Status and auxiliary snapshot identification subsystem."""

from infrastructure.watcher.snapshots.identifier import SnapshotIdentifier
from infrastructure.watcher.snapshots.models import SnapshotCandidate
from infrastructure.watcher.snapshots.registry import (
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
