"""Pure domain package for Elite Dangerous telemetry processing."""

from .exceptions import DomainError, DomainValidationError, TelemetryProcessingError
from .models import TelemetryStreamIdentifier, TelemetryStreamKind

__all__ = [
    "DomainError",
    "DomainValidationError",
    "TelemetryProcessingError",
    "TelemetryStreamIdentifier",
    "TelemetryStreamKind",
]
