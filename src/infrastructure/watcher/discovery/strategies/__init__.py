"""Concrete platform discovery strategies for infrastructure.watcher."""

from __future__ import annotations

from infrastructure.watcher.discovery.strategies.linux import LinuxProtonPathStrategy
from infrastructure.watcher.discovery.strategies.windows import WindowsPathStrategy

__all__ = ["LinuxProtonPathStrategy", "WindowsPathStrategy"]
