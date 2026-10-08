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
from ed_watcher.exceptions import JournalDirectoryAccessError
from ed_watcher.selector import (
    JournalCandidate,
    JournalSelector,
    StreamPosition,
    parse_journal_timestamp,
)
from ed_watcher.watcher import JournalWatcher

__all__ = [
    "DiscoveryResult",
    "InvalidPathOverrideError",
    "JournalCandidate",
    "JournalDirectoryAccessError",
    "JournalPathNotFoundError",
    "JournalSelector",
    "JournalWatcher",
    "PathDiscoverer",
    "PathDiscoveryError",
    "PathDiscoveryStrategy",
    "StreamPosition",
    "SupportedPlatform",
    "UnsupportedPlatformError",
    "WatcherError",
    "parse_journal_timestamp",
]
