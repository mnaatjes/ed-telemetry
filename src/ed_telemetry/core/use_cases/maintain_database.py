"""Use cases for querying database statistics and maintaining persistence storage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..ports.driven.telemetry_driven_port import TelemetryRepositoryPort
from ..ports.driving.telemetry_port import (
    DatabaseMaintenanceResultDTO,
    DatabaseStatsDTO,
    GetDatabaseStatsPort,
    MaintainDatabasePort,
)


class GetDatabaseStatsUseCase(GetDatabaseStatsPort):
    """Stateless interactor retrieving persistence statistics via TelemetryRepositoryPort."""

    def __init__(self, repository: TelemetryRepositoryPort) -> None:
        self._repository = repository

    def get_stats(self) -> DatabaseStatsDTO:
        """Fetch current database statistics."""
        return self._repository.get_database_stats()


class MaintainDatabaseUseCase(MaintainDatabasePort):
    """Stateless interactor executing retention pruning and storage maintenance."""

    def __init__(self, repository: TelemetryRepositoryPort) -> None:
        self._repository = repository

    def maintain(
        self,
        retention_days: int | None = None,
        max_records: int | None = None,
        run_vacuum: bool = False,
    ) -> DatabaseMaintenanceResultDTO:
        """Execute database retention pruning and optional vacuuming."""
        initial_stats = self._repository.get_database_stats()
        initial_size = initial_stats.file_size_bytes

        older_than: datetime | None = None
        if retention_days is not None and retention_days > 0:
            older_than = datetime.now(UTC) - timedelta(days=retention_days)

        pruned = self._repository.prune_events(older_than=older_than, max_records=max_records)

        vacuumed = False
        if run_vacuum:
            self._repository.vacuum()
            vacuumed = True

        final_stats = self._repository.get_database_stats()
        final_size = final_stats.file_size_bytes

        return DatabaseMaintenanceResultDTO(
            pruned_count=pruned,
            vacuumed=vacuumed,
            initial_size_bytes=initial_size,
            final_size_bytes=final_size,
        )
