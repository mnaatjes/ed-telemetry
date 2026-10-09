"""Unit tests for WatcherService and WatcherStatusDTO."""

import threading
from pathlib import Path

import pytest

from domain.ports.watcher import AuditEventHandler, IngestionEventHandler, WatcherPort
from services import BaseApplicationService
from services.bootstrap import build_application_context
from services.context import ApplicationContext
from services.dto import DataTransferObject
from services.dto.watcher import WatcherStatusDTO
from services.exceptions import ServiceDependencyError
from services.watcher import WatcherService


class MockWatcher(WatcherPort):
    """Mock WatcherPort implementation for testing WatcherService in isolation."""

    def __init__(self, is_active: bool = False, journal_dir: Path | None = None) -> None:
        self._is_active = is_active
        self.journal_dir = journal_dir
        self.start_called = False
        self.stop_called = False

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        pass

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        pass

    def start(self) -> None:
        self.start_called = True
        self._is_active = True

    def stop(self) -> None:
        self.stop_called = True
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active


def test_watcher_status_dto_conformance() -> None:
    """Verify WatcherStatusDTO satisfies DataTransferObject protocol."""
    dto = WatcherStatusDTO(is_active=True, journal_dir="/test/path")
    assert isinstance(dto, DataTransferObject)
    assert dto.to_dict() == {
        "is_active": True,
        "journal_dir": "/test/path",
    }


def test_watcher_service_initialization_validation() -> None:
    """Verify WatcherService rejects None watcher dependency."""
    with pytest.raises(ServiceDependencyError, match="WatcherPort dependency cannot be None"):
        WatcherService(watcher=None)  # type: ignore[arg-type]


def test_watcher_service_protocol_conformance() -> None:
    """Verify WatcherService satisfies BaseApplicationService."""
    mock_watcher = MockWatcher()
    service = WatcherService(watcher=mock_watcher)

    assert isinstance(service, BaseApplicationService)
    assert service.service_name == "watcher_service"


def test_watcher_service_status_query() -> None:
    """Verify WatcherService.get_status returns accurate WatcherStatusDTO."""
    mock_watcher = MockWatcher(is_active=False, journal_dir=Path("/path/to/journals"))
    service = WatcherService(watcher=mock_watcher)

    status = service.get_status()
    assert isinstance(status, WatcherStatusDTO)
    assert not status.is_active
    assert status.journal_dir == str(Path("/path/to/journals"))
    assert status.to_dict() == {
        "is_active": False,
        "journal_dir": str(Path("/path/to/journals")),
    }


def test_watcher_service_lifecycle_delegation() -> None:
    """Verify WatcherService start and stop delegate to WatcherPort."""
    mock_watcher = MockWatcher()
    service = WatcherService(watcher=mock_watcher)

    assert not mock_watcher.start_called
    service.start()
    assert mock_watcher.start_called
    assert mock_watcher.is_active

    assert not mock_watcher.stop_called
    service.stop()
    assert mock_watcher.stop_called
    assert not mock_watcher.is_active


def test_application_context_wiring_with_watcher_service() -> None:
    """Verify build_application_context wires WatcherService side-effect-free."""
    threads_before = threading.active_count()
    ctx = build_application_context()

    assert threading.active_count() == threads_before
    assert isinstance(ctx, ApplicationContext)
    assert isinstance(ctx.watcher_service, WatcherService)
    assert ctx.watcher_service in ctx.services
    assert len(ctx.services) == 1

    # Verify status query from context
    status = ctx.watcher_service.get_status()
    assert isinstance(status, WatcherStatusDTO)
    assert not status.is_active
