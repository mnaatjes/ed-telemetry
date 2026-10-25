"""Concrete platform discovery strategies for ed_telemetry.adapters.driven.watcher."""

from __future__ import annotations

from ed_telemetry.adapters.driven.watcher.discovery.strategies.linux import LinuxProtonPathStrategy
from ed_telemetry.adapters.driven.watcher.discovery.strategies.windows import WindowsPathStrategy

__all__ = ["LinuxProtonPathStrategy", "WindowsPathStrategy"]
