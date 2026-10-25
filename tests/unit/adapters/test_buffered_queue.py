"""Unit tests for BufferedQueueAdapter."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from ed_telemetry.adapters.driven.egress.buffered_queue import BufferedQueueAdapter
from ed_telemetry.core.ports.dto import TelemetryPayloadDTO


def _make_payload(topic: str = "telemetry.journal", content: bytes = b"{}") -> TelemetryPayloadDTO:
    return TelemetryPayloadDTO(
        topic=topic,
        timestamp=datetime.now(UTC),
        payload_bytes=content,
        metadata=(("test", "true"),),
    )


class TestBufferedQueueAdapter:
    """Verifies thread-safe buffer mechanics and capacity limits."""

    def test_send_and_poll(self) -> None:
        adapter = BufferedQueueAdapter(maxsize=10)
        p1 = _make_payload(content=b'{"event":"Docked"}')
        adapter.send(p1)

        assert adapter.queue_size() == 1
        polled = adapter.poll(timeout=0.1)
        assert polled is not None
        assert polled.payload_bytes == b'{"event":"Docked"}'
        assert adapter.queue_size() == 0

    def test_get_batch_drains_events(self) -> None:
        adapter = BufferedQueueAdapter(maxsize=10)
        for i in range(5):
            adapter.send(_make_payload(content=f'{{"i":{i}}}'.encode()))

        batch = adapter.get_batch(limit=3)
        assert len(batch.events) == 3
        assert batch.remaining_count == 2
        assert batch.dropped_count == 0

        batch_rest = adapter.get_batch(limit=10)
        assert len(batch_rest.events) == 2
        assert batch_rest.remaining_count == 0

    def test_saturation_drops_oldest(self) -> None:
        adapter = BufferedQueueAdapter(maxsize=3)
        for i in range(5):
            adapter.send(_make_payload(content=f'{{"val":{i}}}'.encode()))

        assert adapter.queue_size() == 3
        assert adapter.dropped_count == 2

        batch = adapter.get_batch(limit=10)
        assert len(batch.events) == 3
        # Oldest (0 and 1) were dropped; remaining should be 2, 3, 4
        payloads = [e.payload_bytes for e in batch.events]
        assert payloads == [b'{"val":2}', b'{"val":3}', b'{"val":4}']
        assert batch.dropped_count == 2

    def test_concurrent_producers_and_consumers(self) -> None:
        adapter = BufferedQueueAdapter(maxsize=500)
        num_items = 200

        def producer() -> None:
            for i in range(num_items):
                adapter.send(_make_payload(content=f'{{"n":{i}}}'.encode()))

        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=producer)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert adapter.queue_size() == num_items * 2
        batch = adapter.get_batch(limit=500)
        assert len(batch.events) == num_items * 2
