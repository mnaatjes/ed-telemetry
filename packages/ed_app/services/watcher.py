"""Application service managing and querying inbound watcher telemetry."""

from ed_domain.ports.watcher import WatcherPort

from ed_app.dto.watcher import WatcherStatusDTO
from ed_app.exceptions import ServiceDependencyError
from ed_app.services.base import BaseApplicationService


class WatcherService(BaseApplicationService):
    """Application service managing and querying inbound watcher telemetry."""

    def __init__(self, watcher: WatcherPort) -> None:
        if watcher is None:
            raise ServiceDependencyError("WatcherPort dependency cannot be None")
        self._watcher = watcher

    @property
    def service_name(self) -> str:
        return "watcher_service"

    def get_status(self) -> WatcherStatusDTO:
        """Query current operational state of the watcher adapter."""
        journal_dir_path = getattr(self._watcher, "journal_dir", None)
        journal_str = str(journal_dir_path) if journal_dir_path is not None else None
        return WatcherStatusDTO(
            is_active=self._watcher.is_active,
            journal_dir=journal_str,
        )

    def start(self) -> None:
        """Start inbound telemetry watching."""
        self._watcher.start()

    def stop(self) -> None:
        """Stop inbound telemetry watching."""
        self._watcher.stop()
