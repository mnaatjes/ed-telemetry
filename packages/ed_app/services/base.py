"""Application service base abstractions and protocols."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseApplicationService(Protocol):
    """Protocol satisfied by all application services."""

    @property
    def service_name(self) -> str:
        """Unique service identifier string."""
        ...
