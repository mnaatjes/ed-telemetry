"""Watcher Driven Adapter Registry for Inbound Journal and File Watchers.

Governed by ADR 0014 and SDD-012.
"""

from __future__ import annotations

from domain.ports.watcher import WatcherPort
from services.registry.base import BaseAdapterRegistry


class WatcherRegistry(BaseAdapterRegistry[WatcherPort]):
    """Registry managing inbound telemetry file watchers (1 -> 1 active stream)."""

    def __init__(self) -> None:
        super().__init__()
        self._active_key: str | None = None

    def register(self, key: str, adapter: WatcherPort) -> None:
        """Register a watcher adapter, designating the first registered as active."""
        super().register(key, adapter)
        if self._active_key is None:
            self._active_key = key

    def get_active(self) -> WatcherPort:
        """Return the designated active watcher adapter."""
        if self._active_key is None:
            raise KeyError("No active watcher configured in WatcherRegistry.")
        return self.get(self._active_key)

    def set_active(self, key: str) -> None:
        """Set the active watcher adapter to a registered key."""
        if key not in self:
            raise KeyError(f"Cannot activate unregistered watcher key '{key}'.")
        self._active_key = key

    @property
    def active_key(self) -> str | None:
        """Return the key of the currently active watcher adapter, if any."""
        return self._active_key
