"""Use case for querying the operational status of telemetry watchers."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import WatcherPort
from ..ports.driving.telemetry_port import GetWatcherStatusPort, WatcherStatusDTO


class GetWatcherStatusUseCase(GetWatcherStatusPort):
    """Stateless interactor inspecting watcher operational state."""

    def __init__(self, watcher: WatcherPort) -> None:
        self._watcher = watcher

    def get_status(self) -> WatcherStatusDTO:
        """Query current status and return immutable DTO."""
        journal_dir = self._watcher.journal_dir
        active_journal: str | None = None
        if journal_dir is not None:
            try:
                journal_list = self._watcher.list_journals()
                active_journal = journal_list.active_journal
            except Exception:
                pass
        return WatcherStatusDTO(
            is_active=self._watcher.is_active,
            active_journal=active_journal,
            monitored_directory=str(journal_dir) if journal_dir is not None else None,
        )
