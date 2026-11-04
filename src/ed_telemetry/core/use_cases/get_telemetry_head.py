"""Use case for retrieving consolidated point-in-time head state snapshot."""

from __future__ import annotations

from datetime import UTC, datetime

from ..ports.driven.telemetry_driven_port import TelemetryRepositoryPort
from ..ports.driving.telemetry_port import (
    AuxiliarySnapshotDTO,
    GetAuxiliarySnapshotPort,
    GetLatestGameStatusPort,
    GetTelemetryHeadPort,
    GetWatcherStatusPort,
    TelemetryHeadDTO,
    TelemetryQueryDTO,
)

STANDARD_SNAPSHOT_NAMES = (
    "NavRoute.json",
    "Market.json",
    "Cargo.json",
    "Shipyard.json",
    "Outfitting.json",
    "Status.json",
    "ModulesInfo.json",
)


class GetTelemetryHeadUseCase(GetTelemetryHeadPort):
    """Retrieves point-in-time head state without dequeuing or mutating streaming buffers."""

    def __init__(
        self,
        repository: TelemetryRepositoryPort,
        game_status_port: GetLatestGameStatusPort,
        aux_snapshot_port: GetAuxiliarySnapshotPort,
        watcher_status_port: GetWatcherStatusPort,
    ) -> None:
        self._repository = repository
        self._game_status_port = game_status_port
        self._aux_snapshot_port = aux_snapshot_port
        self._watcher_status_port = watcher_status_port

    def get_head(self) -> TelemetryHeadDTO:
        """Assemble latest journal event, active status, and known snapshots."""
        latest_records = self._repository.find_events(
            TelemetryQueryDTO(topic="telemetry.journal", limit=1, order="desc")
        )
        latest_event = latest_records[0] if latest_records else None

        watcher_status = self._watcher_status_port.get_status()
        status_dto = self._game_status_port.get_game_status()

        snapshots: dict[str, AuxiliarySnapshotDTO] = {}
        for snap_name in STANDARD_SNAPSHOT_NAMES:
            try:
                snap = self._aux_snapshot_port.get_snapshot(snap_name)
                if snap.exists:
                    key = snap_name.replace(".json", "")
                    snapshots[key] = snap
            except Exception:
                continue

        return TelemetryHeadDTO(
            timestamp=datetime.now(UTC),
            active_journal=watcher_status.active_journal,
            latest_journal_event=latest_event,
            game_status=status_dto,
            snapshots=snapshots,
        )
