"""Use case for inspecting an auxiliary state snapshot."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import WatcherPort
from ..ports.driving.telemetry_port import (
    AuxiliarySnapshotDTO,
    GetAuxiliarySnapshotPort,
)


class GetAuxiliarySnapshotUseCase(GetAuxiliarySnapshotPort):
    """Stateless interactor retrieving specific auxiliary snapshot payload."""

    def __init__(self, watcher: WatcherPort) -> None:
        self._watcher = watcher

    def get_snapshot(self, snapshot_name: str) -> AuxiliarySnapshotDTO:
        """Inspect and return specified snapshot data."""
        return self._watcher.read_auxiliary_snapshot(snapshot_name)
