"""Composition root and application context factory."""

from pathlib import Path

from ed_domain.engine import TelemetryEngine
from ed_egress.transmitter import NullTransmitter
from ed_watcher.watcher import FileSystemWatcher

from ed_app.context import ApplicationContext
from ed_app.services.watcher import WatcherService


def build_engine(journal_dir: Path | None = None) -> TelemetryEngine:
    """Instantiate concrete adapters and inject into the core domain engine.

    Guaranteed side-effect-free: does not bind network sockets,
    create files, or launch background threads during construction.
    """
    watcher = FileSystemWatcher(journal_dir=journal_dir)
    egress_adapters = [NullTransmitter()]
    return TelemetryEngine(watcher=watcher, egress_ports=egress_adapters)


def build_application_context(journal_dir: Path | None = None) -> ApplicationContext:
    """Instantiate and assemble the full application context.

    Guaranteed side-effect-free: does not bind network sockets,
    create files, or launch background threads during construction.
    """
    engine = build_engine(journal_dir=journal_dir)
    watcher_service = WatcherService(watcher=engine.watcher)
    return ApplicationContext(
        engine=engine,
        watcher_service=watcher_service,
        services=(watcher_service,),
    )
