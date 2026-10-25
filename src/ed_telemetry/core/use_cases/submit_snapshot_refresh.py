"""Use case for triggering an immediate snapshot re-read hint in the watcher."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import WatcherPort
from ..ports.driving.telemetry_port import (
    HintSubmissionDTO,
    SubmitSnapshotRefreshPort,
)


class SubmitSnapshotRefreshUseCase(SubmitSnapshotRefreshPort):
    """Stateless interactor submitting snapshot refresh hints."""

    def __init__(self, watcher: WatcherPort) -> None:
        self._watcher = watcher

    def refresh_snapshot(self, snapshot_name: str) -> HintSubmissionDTO:
        """Submit HINT_SNAPSHOT to reactor queue for target file."""
        return self._watcher.submit_ingest_hint("hint_snapshot", target_name=snapshot_name)
