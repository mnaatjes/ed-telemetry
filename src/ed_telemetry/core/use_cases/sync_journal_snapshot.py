"""Use case for synchronizing point-in-time telemetry journal snapshots."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import EgressPort, WatcherPort
from ..ports.driving.telemetry_port import SnapshotSyncResultDTO, SyncJournalSnapshotPort


class SyncJournalSnapshotUseCase(SyncJournalSnapshotPort):
    """Stateless interactor for point-in-time snapshot interrogation and sync."""

    def __init__(self, watcher: WatcherPort, egress: EgressPort) -> None:
        self._watcher = watcher
        self._egress = egress

    def sync_snapshots(self) -> SnapshotSyncResultDTO:
        """Inspect active snapshot files and return synchronization summary."""
        return SnapshotSyncResultDTO(
            files_inspected=0,
            payloads_emitted=0,
            active_journal_file=None,
        )
