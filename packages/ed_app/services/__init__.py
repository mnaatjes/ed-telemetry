"""Service definitions and protocols for ed_app."""

from ed_app.services.base import BaseApplicationService
from ed_app.services.watcher import WatcherService

__all__ = ["BaseApplicationService", "WatcherService"]
