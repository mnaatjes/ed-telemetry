"""Public API for infrastructure.watcher OS path discovery subsystem."""

from __future__ import annotations

from infrastructure.watcher.discovery.coordinator import PathDiscoverer
from infrastructure.watcher.discovery.exceptions import (
    InvalidPathOverrideError,
    JournalPathNotFoundError,
    PathDiscoveryError,
    UnsupportedPlatformError,
    WatcherError,
)
from infrastructure.watcher.discovery.models import DiscoveryResult, SupportedPlatform
from infrastructure.watcher.discovery.protocols import PathDiscoveryStrategy

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
