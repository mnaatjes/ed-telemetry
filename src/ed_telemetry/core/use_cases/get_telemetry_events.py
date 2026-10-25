"""Use case for polling and batch-reading buffered telemetry events."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import EventQueuePort
from ..ports.driving.telemetry_port import GetTelemetryEventsPort, TelemetryBatchDTO


class GetTelemetryEventsUseCase(GetTelemetryEventsPort):
    """Stateless interactor consuming buffered telemetry events on behalf of driving adapters."""

    def __init__(self, queue: EventQueuePort) -> None:
        self._queue = queue

    def get_events(self, limit: int = 100, timeout: float | None = None) -> TelemetryBatchDTO:
        """Poll and return a batch of telemetry events from the driven queue."""
        return self._queue.get_batch(limit=limit, timeout=timeout)
