"""Abstract ports for outbound telemetry egress.

Governed by ADR 0015 and SDD-013.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.ports.base import DiscreteSinkPort

__all__ = ["EgressPort"]


@runtime_checkable
class EgressPort(DiscreteSinkPort, Protocol):
    """Contract for transmitting telemetry payloads to external endpoints.

    Specializes DiscreteSinkPort (pure outbound sink archetype).
    Zero lifecycle hooks declared.
    """
