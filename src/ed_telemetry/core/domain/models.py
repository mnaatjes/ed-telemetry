"""Pure domain models for telemetry processing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .exceptions import DomainValidationError


class TelemetryStreamKind(StrEnum):
    """Canonical categories of telemetry streams."""

    JOURNAL = "journal"
    STATUS = "status"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True)
class TelemetryStreamIdentifier:
    """Self-validating domain identifier for a telemetry event stream."""

    kind: TelemetryStreamKind
    session_id: str

    def __post_init__(self) -> None:
        """Validate non-empty session identifier invariant."""
        if not self.session_id or not self.session_id.strip():
            raise DomainValidationError("session_id cannot be empty or blank")
