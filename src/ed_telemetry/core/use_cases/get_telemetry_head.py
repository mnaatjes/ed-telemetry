"""Use case for retrieving consolidated point-in-time head state snapshot."""

from __future__ import annotations

from datetime import UTC, datetime

from ..ports.driven.telemetry_driven_port import TelemetryRepositoryPort, WatcherPort
from ..ports.driving.telemetry_port import (
    AuxiliarySnapshotDTO,
    GetAuxiliarySnapshotPort,
    GetLatestGameStatusPort,
    GetTelemetryHeadPort,
    GetTelemetryStatePort,
    GetWatcherStatusPort,
    TelemetryHeadDTO,
    TelemetryRecordDTO,
)
from ..state.sequence import StateSequenceTracker

STANDARD_SNAPSHOT_NAMES = (
    "NavRoute.json",
    "Market.json",
    "Cargo.json",
    "Shipyard.json",
    "Outfitting.json",
    "Status.json",
    "ModulesInfo.json",
)


class GetTelemetryHeadUseCase(GetTelemetryHeadPort, GetTelemetryStatePort):
    """Retrieves point-in-time head state without dequeuing or mutating streaming buffers."""

    def __init__(
        self,
        repository: TelemetryRepositoryPort | None = None,
        game_status_port: GetLatestGameStatusPort | None = None,
        aux_snapshot_port: GetAuxiliarySnapshotPort | None = None,
        watcher_status_port: GetWatcherStatusPort | None = None,
        watcher_port: WatcherPort | None = None,
        sequence_tracker: StateSequenceTracker | None = None,
    ) -> None:
        self._repository = repository
        self._game_status_port = game_status_port
        self._aux_snapshot_port = aux_snapshot_port
        self._watcher_status_port = watcher_status_port
        self._watcher_port = watcher_port
        self._sequence_tracker = sequence_tracker or StateSequenceTracker()

    def get_state(self) -> TelemetryHeadDTO:
        """Assemble latest journal event, active status, and known snapshots 100% in-memory."""
        latest_event: TelemetryRecordDTO | None = None
        if self._watcher_port is not None:
            latest_event = self._watcher_port.read_active_journal_tail()

        # Invariant 1 (Zero-DB Head Hydration):
        # We NEVER fall back to self._repository.find_events().
        # If no journal is open, latest_event remains None.

        active_journal: str | None = None
        if self._watcher_status_port is not None:
            watcher_status = self._watcher_status_port.get_status()
            active_journal = watcher_status.active_journal

        status_dto = self._game_status_port.get_game_status() if self._game_status_port is not None else None

        snapshots: dict[str, AuxiliarySnapshotDTO] = {}
        if self._aux_snapshot_port is not None:
            for snap_name in STANDARD_SNAPSHOT_NAMES:
                try:
                    snap = self._aux_snapshot_port.get_snapshot(snap_name)
                    if snap.exists:
                        key = snap_name.replace(".json", "")
                        snapshots[key] = snap
                except Exception:
                    continue

        seq = self._sequence_tracker.current_sequence

        return TelemetryHeadDTO(
            timestamp=datetime.now(UTC),
            active_journal=active_journal,
            latest_journal_event=latest_event,
            game_status=status_dto,
            snapshots=snapshots,
            state_sequence=seq,
        )

    def get_head(self) -> TelemetryHeadDTO:
        """Backward-compatible alias for get_state."""
        return self.get_state()
