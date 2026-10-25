"""Use case for querying historical telemetry events from persistence."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import TelemetryRepositoryPort
from ..ports.driving.telemetry_port import (
    FindTelemetryEventsPort,
    TelemetryQueryDTO,
    TelemetryRecordDTO,
)


class FindTelemetryEventsUseCase(FindTelemetryEventsPort):
    """Stateless interactor querying historical events via TelemetryRepositoryPort."""

    def __init__(self, repository: TelemetryRepositoryPort) -> None:
        self._repository = repository

    def find_events(self, query: TelemetryQueryDTO) -> tuple[TelemetryRecordDTO, ...]:
        """Fetch historical records matching query criteria."""
        return self._repository.find_events(query=query)
