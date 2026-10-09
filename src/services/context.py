"""Application Context holding domain engine and registered application services."""

from dataclasses import dataclass
from typing import Any

from domain.engine import TelemetryEngine
from services.watcher import WatcherService


@dataclass(frozen=True)
class ApplicationContext:
    """Immutable application context holding the domain engine and registered services."""

    engine: TelemetryEngine
    watcher_service: WatcherService
    services: tuple[Any, ...] = ()
