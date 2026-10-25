"""Use case for streaming real-time telemetry events from the driven queue."""

from __future__ import annotations

from collections.abc import Iterator

from ..ports.driven.telemetry_driven_port import EventQueuePort
from ..ports.driving.telemetry_port import GetTelemetryStreamPort, TelemetryPayloadDTO


class GetTelemetryStreamUseCase(GetTelemetryStreamPort):
    """Stateless interactor yielding live telemetry events from EventQueuePort."""

    def __init__(self, queue: EventQueuePort) -> None:
        self._queue = queue

    def stream_events(self, timeout: float | None = 1.0) -> Iterator[TelemetryPayloadDTO]:
        """Yield live telemetry payloads as they arrive on the queue."""
        while True:
            ev = self._queue.poll(timeout=timeout)
            if ev is not None:
                yield ev
