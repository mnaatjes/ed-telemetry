"""Core domain package for Elite Dangerous telemetry processing."""

from domain.engine import TelemetryEngine
from domain.ports.egress import EgressPort
from domain.ports.watcher import WatcherPort

__version__ = "0.3.0"

__all__ = ["TelemetryEngine", "WatcherPort", "EgressPort", "__version__"]
