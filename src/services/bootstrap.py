"""Composition root and application context factory."""

from pathlib import Path

from domain.engine import TelemetryEngine
from infrastructure.egress.transmitter import NullTransmitter
from infrastructure.watcher.watcher import FileSystemWatcher
from services.context import ApplicationContext
from services.registry.egress import EgressRegistry
from services.registry.watcher import WatcherRegistry
from services.watcher import WatcherService


def build_engine(journal_dir: Path | None = None) -> TelemetryEngine:
    """Instantiate concrete adapters and inject into the core domain engine.

    Guaranteed side-effect-free: does not bind network sockets,
    create files, or launch background threads during construction.
    """
    # 1. Instantiate concrete driven adapters (src/infrastructure/)
    watcher_adapter = FileSystemWatcher(journal_dir=journal_dir)
    null_transmitter = NullTransmitter()

    # 2. Populate driven adapter registries (src/services/registry/)
    watcher_registry = WatcherRegistry()
    watcher_registry.register("primary_watcher", watcher_adapter)

    egress_registry = EgressRegistry()
    egress_registry.register("null_transmitter", null_transmitter)

    # 3. Inject adapters into engine from registries
    return TelemetryEngine(
        watcher=watcher_registry.get_active(),
        egress_ports=list(egress_registry.get_transmitters()),
    )


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
