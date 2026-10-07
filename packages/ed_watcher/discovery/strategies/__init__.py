"""Concrete platform discovery strategies for ed_watcher."""

from __future__ import annotations

from ed_watcher.discovery.strategies.linux import LinuxProtonPathStrategy
from ed_watcher.discovery.strategies.windows import WindowsPathStrategy

__all__ = ["LinuxProtonPathStrategy", "WindowsPathStrategy"]
