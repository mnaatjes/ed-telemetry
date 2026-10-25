"""Use case for discovering the Elite Dangerous journal directory."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import WatcherPort
from ..ports.driving.telemetry_port import FindJournalPathPort, JournalPathDTO


class FindJournalPathUseCase(FindJournalPathPort):
    """Stateless interactor discovering local journal path."""

    def __init__(self, watcher: WatcherPort) -> None:
        self._watcher = watcher

    def find_path(self, override_path: str | None = None) -> JournalPathDTO:
        """Resolve and return journal directory path."""
        return self._watcher.discover_path(override_path=override_path)
