"""CLI driving adapter for telemetry inspection."""

from __future__ import annotations

from typing import Any

from ed_telemetry.core.ports.driving.telemetry_port import GetWatcherStatusPort


class CliTelemetryAdapter:
    """Driving adapter executing watcher status inspections for CLI runtime."""

    def __init__(self, watcher_status_port: GetWatcherStatusPort) -> None:
        self._watcher_status_port = watcher_status_port

    def run(self) -> tuple[int, dict[str, Any]]:
        """Query watcher status and format response."""
        status = self._watcher_status_port.get_status()
        payload: dict[str, Any] = {
            "is_active": status.is_active,
            "active_journal": status.active_journal,
            "monitored_directory": status.monitored_directory,
        }
        return 0, payload
