"""Use case for listing journal files in chronological order."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import WatcherPort
from ..ports.driving.telemetry_port import GetJournalFilesPort, JournalFileListDTO


class GetJournalFilesUseCase(GetJournalFilesPort):
    """Stateless interactor listing candidate journal files."""

    def __init__(self, watcher: WatcherPort) -> None:
        self._watcher = watcher

    def get_journals(self) -> JournalFileListDTO:
        """Scan directory and return sorted journal files with metadata."""
        return self._watcher.list_journals()
