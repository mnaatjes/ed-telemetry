"""Composition Root: Assembles dependencies into a runnable TelemetryEngine."""

from ed_domain.engine import TelemetryEngine
from ed_egress.transmitter import NullTransmitter
from ed_watcher.watcher import JournalWatcher


def build_engine() -> TelemetryEngine:
    """Instantiate concrete adapters and inject into the core domain engine.

    Guaranteed side-effect-free: does not bind network sockets,
    create files, or launch background threads during construction.
    """
    watcher = JournalWatcher()
    egress_adapters = [NullTransmitter()]
    return TelemetryEngine(watcher=watcher, egress_ports=egress_adapters)
