"""In-memory test double for EgressPort."""

from __future__ import annotations

from ed_telemetry.core.ports.driven.telemetry_driven_port import EgressPort, TelemetryPayloadDTO


class FakeEgressAdapter(EgressPort):
    """In-memory test double for EgressPort satisfying HEXA-TRUTH-27."""

    def __init__(self) -> None:
        self.sent_payloads: list[TelemetryPayloadDTO] = []

    def send(self, payload: TelemetryPayloadDTO) -> None:
        """Record payload in memory."""
        self.sent_payloads.append(payload)
