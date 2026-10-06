"""Core telemetry coordination engine."""

from collections.abc import Sequence

from ed_domain.ports.egress import EgressPort
from ed_domain.ports.watcher import WatcherPort


class TelemetryEngine:
    """Coordinates telemetry ingestion from watchers and dispatch to egress ports."""

    def __init__(self, watcher: WatcherPort, egress_ports: Sequence[EgressPort] | None = None) -> None:
        self.watcher = watcher
        self.egress_ports = list(egress_ports) if egress_ports is not None else []
        self._running = False

    def start(self) -> None:
        """Start the telemetry engine and inbound watcher."""
        self._running = True
        self.watcher.start()

    def stop(self) -> None:
        """Stop the inbound watcher and telemetry engine."""
        self.watcher.stop()
        self._running = False

    @property
    def is_running(self) -> bool:
        """Return True if the engine is running."""
        return self._running
