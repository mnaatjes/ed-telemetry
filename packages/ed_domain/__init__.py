"""Core domain package for Elite Dangerous telemetry processing."""

from ed_domain.engine import TelemetryEngine
from ed_domain.ports.egress import EgressPort
from ed_domain.ports.watcher import WatcherPort

__version__ = "0.2.0"

__all__ = ["TelemetryEngine", "WatcherPort", "EgressPort", "__version__"]
