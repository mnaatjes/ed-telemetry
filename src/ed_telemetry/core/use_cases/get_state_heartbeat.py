"""Use case for retrieving state delta heartbeat."""

from __future__ import annotations

from datetime import UTC, datetime

from ..ports.driven.telemetry_driven_port import WatcherPort
from ..ports.driving.telemetry_port import (
    GetAuxiliarySnapshotPort,
    GetLatestGameStatusPort,
    GetStateHeartbeatPort,
    GetWatcherStatusPort,
    TelemetryHeartbeatDTO,
)
from ..state.sequence import StateSequenceTracker

STANDARD_SNAPSHOT_NAMES = (
    "NavRoute.json",
    "Market.json",
    "Cargo.json",
    "Shipyard.json",
    "Outfitting.json",
    "ModulesInfo.json",
)


class GetStateHeartbeatUseCase(GetStateHeartbeatPort):
    """Retrieves ultra-lightweight state synchronization heartbeat."""

    def __init__(
        self,
        game_status_port: GetLatestGameStatusPort | None = None,
        aux_snapshot_port: GetAuxiliarySnapshotPort | None = None,
        watcher_status_port: GetWatcherStatusPort | None = None,
        watcher_port: WatcherPort | None = None,
        sequence_tracker: StateSequenceTracker | None = None,
    ) -> None:
        self._game_status_port = game_status_port
        self._aux_snapshot_port = aux_snapshot_port
        self._watcher_status_port = watcher_status_port
        self._watcher_port = watcher_port
        self._sequence_tracker = sequence_tracker or StateSequenceTracker()

    def get_heartbeat(self) -> TelemetryHeartbeatDTO:
        """Assemble lightweight state heartbeat (< 200 bytes)."""
        active_journal: str | None = None
        if self._watcher_status_port is not None:
            watcher_status = self._watcher_status_port.get_status()
            active_journal = watcher_status.active_journal

        latest_event_id: str | None = None
        if self._watcher_port is not None:
            tail = self._watcher_port.read_active_journal_tail()
            if tail is not None:
                latest_event_id = tail.event_id

        status_hash: str | None = None
        if self._game_status_port is not None:
            status_snap = self._game_status_port.get_game_status()
            if status_snap.exists:
                status_hash = status_snap.raw_hash

        snapshot_hashes: dict[str, str] = {}
        if self._aux_snapshot_port is not None:
            for snap_name in STANDARD_SNAPSHOT_NAMES:
                try:
                    snap = self._aux_snapshot_port.get_snapshot(snap_name)
                    if snap.exists and snap.raw_hash:
                        key = snap_name.replace(".json", "")
                        snapshot_hashes[key] = snap.raw_hash
                except Exception:
                    continue

        seq = self._sequence_tracker.current_sequence

        return TelemetryHeartbeatDTO(
            state_sequence=seq,
            timestamp=datetime.now(UTC),
            active_journal=active_journal,
            latest_event_id=latest_event_id,
            status_hash=status_hash,
            snapshot_hashes=snapshot_hashes,
        )
