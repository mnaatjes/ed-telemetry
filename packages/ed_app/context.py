"""Application Context holding domain engine and registered application services."""

from dataclasses import dataclass
from typing import Any

from ed_domain.engine import TelemetryEngine


@dataclass(frozen=True)
class ApplicationContext:
    """Immutable application context holding the domain engine and registered services.

    In this scaffolding phase, services is empty by default until concrete
    feature services are onboarded.
    """

    engine: TelemetryEngine
    services: tuple[Any, ...] = ()
