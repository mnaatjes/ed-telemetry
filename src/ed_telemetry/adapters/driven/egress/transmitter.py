"""Outbound egress transmitter adapter satisfying EgressPort."""

from __future__ import annotations

from ed_telemetry.core.ports.driven.telemetry_driven_port import EgressPort
from ed_telemetry.core.ports.dto.telemetry_dto import TelemetryPayloadDTO


class NullTransmitter(EgressPort):
    """Minimal outbound transmitter satisfying EgressPort."""

    def __init__(self) -> None:
        self.sent_payloads: list[TelemetryPayloadDTO] = []

    def send(self, payload: TelemetryPayloadDTO) -> None:
        """Record payload in memory without network side-effects."""
        self.sent_payloads.append(payload)
