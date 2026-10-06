"""Abstract ports for outbound telemetry egress."""

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EgressPort(Protocol):
    """Contract for transmitting telemetry payloads to external endpoints."""

    def send(self, payload: Mapping[str, Any]) -> None:
        """Transmit a payload to downstream consumers."""
        ...
