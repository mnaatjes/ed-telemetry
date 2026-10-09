"""Journal watcher adapter package."""

from ed_watcher.discovery import (
    DiscoveryResult,
    InvalidPathOverrideError,
    JournalPathNotFoundError,
    PathDiscoverer,
    PathDiscoveryError,
    PathDiscoveryStrategy,
    SupportedPlatform,
    UnsupportedPlatformError,
    WatcherError,
)
from ed_watcher.exceptions import (
    InvalidSnapshotFileTypeError,
    JournalDirectoryAccessError,
    SnapshotCollisionError,
    SnapshotDirectoryAccessError,
    SnapshotIdentificationError,
    SnapshotRegistrationError,
    UnregisteredSnapshotError,
)
from ed_watcher.selector import (
    JournalCandidate,
    JournalSelector,
    StreamPosition,
    parse_journal_timestamp,
)
from ed_watcher.snapshots import (
    CANONICAL_AUXILIARY_SNAPSHOTS,
    CANONICAL_STATUS_FILE,
    SnapshotCandidate,
    SnapshotIdentifier,
    SnapshotRegistry,
)
from ed_watcher.watcher import JournalWatcher

__all__ = [
    "CANONICAL_AUXILIARY_SNAPSHOTS",
    "CANONICAL_STATUS_FILE",
    "DiscoveryResult",
    "InvalidPathOverrideError",
    "InvalidSnapshotFileTypeError",
    "JournalCandidate",
    "JournalDirectoryAccessError",
    "JournalPathNotFoundError",
    "JournalSelector",
    "JournalWatcher",
    "PathDiscoverer",
    "PathDiscoveryError",
    "PathDiscoveryStrategy",
    "SnapshotCandidate",
    "SnapshotCollisionError",
    "SnapshotDirectoryAccessError",
    "SnapshotIdentificationError",
    "SnapshotIdentifier",
    "SnapshotRegistrationError",
    "SnapshotRegistry",
    "StreamPosition",
    "SupportedPlatform",
    "UnregisteredSnapshotError",
    "UnsupportedPlatformError",
    "WatcherError",
    "parse_journal_timestamp",
]
