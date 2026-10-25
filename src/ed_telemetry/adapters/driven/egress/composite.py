"""Composite egress adapter distributing outbound telemetry payloads to multiple sinks."""

from __future__ import annotations

from ed_telemetry.core.ports.driven.telemetry_driven_port import EgressPort
from ed_telemetry.core.ports.dto.telemetry_dto import TelemetryPayloadDTO


class CompositeEgressAdapter(EgressPort):
    """Fans out outbound telemetry payloads across multiple discrete egress adapters."""

    def __init__(self, sinks: tuple[EgressPort, ...] | list[EgressPort]) -> None:
        self._sinks = tuple(sinks)

    def send(self, payload: TelemetryPayloadDTO) -> None:
        """Forward payload to every registered sink."""
        for sink in self._sinks:
            sink.send(payload)
