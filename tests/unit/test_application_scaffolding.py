"""Unit tests for Application Service Layer scaffolding and boundary contracts."""

import threading
from dataclasses import FrozenInstanceError, dataclass

import pytest
from ed_app.bootstrap import build_application_context
from ed_app.context import ApplicationContext
from ed_app.dto import DataTransferObject
from ed_app.exceptions import (
    ApplicationServiceError,
    ServiceDependencyError,
    ServicePayloadError,
    ServiceStateError,
)
from ed_app.services import BaseApplicationService
from ed_domain.engine import TelemetryEngine


def test_build_application_context_instantiation() -> None:
    """Verify build_application_context creates a valid, side-effect-free ApplicationContext."""
    initial_threads = threading.active_count()
    ctx = build_application_context()

    assert threading.active_count() == initial_threads
    assert isinstance(ctx, ApplicationContext)
    assert isinstance(ctx.engine, TelemetryEngine)
    assert ctx.services == ()
    assert not ctx.engine.is_running


def test_application_context_immutability() -> None:
    """Verify that ApplicationContext is a frozen dataclass rejecting mutation."""
    ctx = build_application_context()
    with pytest.raises(FrozenInstanceError):
        ctx.engine = None  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        ctx.services = ()  # type: ignore[misc]


def test_dto_protocol_conformance() -> None:
    """Verify that DataTransferObject runtime-checkable protocol operates as expected."""

    @dataclass(frozen=True)
    class SampleDTO:
        id: str
        value: int

        def to_dict(self) -> dict[str, object]:
            return {"id": self.id, "value": self.value}

    dto = SampleDTO(id="test-1", value=42)
    assert isinstance(dto, DataTransferObject)
    assert dto.to_dict() == {"id": "test-1", "value": 42}

    class NonConformingDTO:
        pass

    assert not isinstance(NonConformingDTO(), DataTransferObject)


def test_base_application_service_protocol_conformance() -> None:
    """Verify that BaseApplicationService protocol validates service implementations."""

    class DummyService:
        @property
        def service_name(self) -> str:
            return "dummy_service"

    srv = DummyService()
    assert isinstance(srv, BaseApplicationService)
    assert srv.service_name == "dummy_service"

    class InvalidService:
        pass

    assert not isinstance(InvalidService(), BaseApplicationService)


def test_application_service_exception_hierarchy() -> None:
    """Verify that all application exceptions inherit from ApplicationServiceError."""
    assert issubclass(ServiceDependencyError, ApplicationServiceError)
    assert issubclass(ServiceStateError, ApplicationServiceError)
    assert issubclass(ServicePayloadError, ApplicationServiceError)
    assert issubclass(ApplicationServiceError, Exception)

    err = ServiceDependencyError("Dependency unavailable")
    assert isinstance(err, ApplicationServiceError)
    assert str(err) == "Dependency unavailable"
