"""Base exception hierarchy for the ed_app application service layer."""


class ApplicationServiceError(Exception):
    """Base exception for all application service errors."""


class ServiceDependencyError(ApplicationServiceError):
    """Raised when an uninitialized or broken dependency is encountered."""


class ServiceStateError(ApplicationServiceError):
    """Raised when an operation is invalid for the current service lifecycle state."""


class ServicePayloadError(ApplicationServiceError):
    """Raised when input parameters fail domain validation constraints."""
