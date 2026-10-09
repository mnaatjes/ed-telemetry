"""Outbound egress transmitter adapter."""

from collections.abc import Mapping
from typing import Any


class NullTransmitter:
    """Minimal outbound transmitter satisfying EgressPort."""

    def __init__(self) -> None:
        self.sent_payloads: list[Mapping[str, Any]] = []

    def send(self, payload: Mapping[str, Any]) -> None:
        """Record payload in memory without network side-effects."""
        self.sent_payloads.append(payload)
