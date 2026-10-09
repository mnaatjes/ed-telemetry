"""Application orchestrator, CLI entry point, FastAPI REST server, and MCP tool provider."""

from ed_app.bootstrap import build_application_context, build_engine
from ed_app.context import ApplicationContext
from ed_app.dto.watcher import WatcherStatusDTO
from ed_app.exceptions import (
    ApplicationServiceError,
    ServiceDependencyError,
    ServicePayloadError,
    ServiceStateError,
)
from ed_app.services.watcher import WatcherService

__all__ = [
    "ApplicationContext",
    "ApplicationServiceError",
    "ServiceDependencyError",
    "ServicePayloadError",
    "ServiceStateError",
    "WatcherService",
    "WatcherStatusDTO",
    "build_application_context",
    "build_engine",
]
