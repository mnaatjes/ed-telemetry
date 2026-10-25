"""Use case for inspecting the latest Status.json snapshot."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import WatcherPort
from ..ports.driving.telemetry_port import (
    GameStatusSnapshotDTO,
    GetLatestGameStatusPort,
)


class GetLatestGameStatusUseCase(GetLatestGameStatusPort):
    """Stateless interactor retrieving live game status snapshot."""

    def __init__(self, watcher: WatcherPort) -> None:
        self._watcher = watcher

    def get_game_status(self) -> GameStatusSnapshotDTO:
        """Inspect and return Status.json snapshot payload."""
        return self._watcher.read_status_snapshot()
