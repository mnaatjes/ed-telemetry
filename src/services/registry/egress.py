"""Egress Driven Adapter Registry for Outbound Telemetry Transmitters.

Governed by ADR 0014 and SDD-012.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from domain.ports.egress import EgressPort
from services.registry.base import BaseAdapterRegistry


class EgressRegistry(BaseAdapterRegistry[EgressPort]):
    """Registry managing outbound telemetry egress sinks (1 -> N broadcast)."""

    def get_transmitters(self) -> Sequence[EgressPort]:
        """Return all registered egress transmitters in registration order."""
        return self.get_all()

    def broadcast(self, payload: Mapping[str, Any]) -> None:
        """Broadcast payload across all registered egress transmitters."""
        for transmitter in self.get_all():
            transmitter.send(payload)
