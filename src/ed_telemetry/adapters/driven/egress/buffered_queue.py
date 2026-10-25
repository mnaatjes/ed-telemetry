"""Thread-safe in-memory buffered queue adapter satisfying EgressPort and EventQueuePort."""

from __future__ import annotations

import queue
import threading

from ed_telemetry.core.ports.driven.telemetry_driven_port import EgressPort, EventQueuePort
from ed_telemetry.core.ports.dto.telemetry_dto import TelemetryBatchDTO, TelemetryPayloadDTO


class BufferedQueueAdapter(EgressPort, EventQueuePort):
    """Thread-safe in-memory buffer decoupling telemetry ingestion from downstream consumers."""

    def __init__(self, maxsize: int = 10000) -> None:
        self._maxsize = maxsize
        self._queue: queue.Queue[TelemetryPayloadDTO] = queue.Queue(maxsize=maxsize if maxsize > 0 else 0)
        self._lock = threading.Lock()
        self._dropped_count = 0

    def send(self, payload: TelemetryPayloadDTO) -> None:
        """Enqueue an outbound telemetry payload, dropping oldest if saturated."""
        if self._maxsize <= 0:
            self._queue.put(payload)
            return

        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            with self._lock:
                try:
                    # Drop oldest entry to make room for newest telemetry
                    self._queue.get_nowait()
                    self._dropped_count += 1
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(payload)
                except queue.Full:
                    self._dropped_count += 1

    def poll(self, timeout: float | None = None) -> TelemetryPayloadDTO | None:
        """Poll a single telemetry payload from the queue, returning None on timeout."""
        try:
            return self._queue.get(block=timeout is not None and timeout > 0, timeout=timeout)
        except queue.Empty:
            return None

    def get_batch(self, limit: int = 100, timeout: float | None = None) -> TelemetryBatchDTO:
        """Extract a batch of telemetry payloads up to limit, waiting optionally on first event."""
        if limit <= 0:
            limit = 100

        events: list[TelemetryPayloadDTO] = []
        first = self.poll(timeout=timeout)
        if first is not None:
            events.append(first)

        # Drain remaining events without blocking up to limit
        while len(events) < limit:
            try:
                ev = self._queue.get_nowait()
                events.append(ev)
            except queue.Empty:
                break

        with self._lock:
            dropped = self._dropped_count

        return TelemetryBatchDTO(
            events=tuple(events),
            remaining_count=self._queue.qsize(),
            dropped_count=dropped,
        )

    def queue_size(self) -> int:
        """Return the current number of buffered events."""
        return self._queue.qsize()

    @property
    def dropped_count(self) -> int:
        """Return the number of dropped events due to buffer saturation."""
        with self._lock:
            return self._dropped_count
