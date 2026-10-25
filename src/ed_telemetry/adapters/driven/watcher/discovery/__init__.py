"""Public API for ed_telemetry.adapters.driven.watcher OS path discovery subsystem."""

from __future__ import annotations

from ed_telemetry.adapters.driven.watcher.discovery.coordinator import PathDiscoverer
from ed_telemetry.adapters.driven.watcher.discovery.exceptions import (
    InvalidPathOverrideError,
    JournalPathNotFoundError,
    PathDiscoveryError,
    UnsupportedPlatformError,
    WatcherError,
)
from ed_telemetry.adapters.driven.watcher.discovery.models import DiscoveryResult, SupportedPlatform
from ed_telemetry.adapters.driven.watcher.discovery.protocols import PathDiscoveryStrategy

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
