"""Pure domain exception hierarchy for Elite Dangerous telemetry processing."""

from __future__ import annotations


class DomainError(Exception):
    """Base domain exception. All domain errors must inherit from this root."""


class DomainValidationError(DomainError):
    """Raised when an entity or value object fails invariant self-validation."""


class TelemetryProcessingError(DomainError):
    """Raised when raw telemetry payloads fail domain integrity checks."""
