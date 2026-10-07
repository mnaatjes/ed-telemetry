"""Public API for ed_watcher OS path discovery subsystem."""

from __future__ import annotations

from ed_watcher.discovery.coordinator import PathDiscoverer
from ed_watcher.discovery.exceptions import (
    InvalidPathOverrideError,
    JournalPathNotFoundError,
    PathDiscoveryError,
    UnsupportedPlatformError,
    WatcherError,
)
from ed_watcher.discovery.models import DiscoveryResult, SupportedPlatform
from ed_watcher.discovery.protocols import PathDiscoveryStrategy

__all__ = [
    "DiscoveryResult",
    "InvalidPathOverrideError",
    "JournalPathNotFoundError",
    "PathDiscoverer",
    "PathDiscoveryError",
    "PathDiscoveryStrategy",
    "SupportedPlatform",
    "UnsupportedPlatformError",
    "WatcherError",
]
