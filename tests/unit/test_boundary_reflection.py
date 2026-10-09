"""Tests for Runtime Reflection Boundary Validation.

Verifies that the reflection validator properly detects object-tunneling violations
across Junctions 1-4 and asserts the presence of the active TelemetryEngine leak
on ApplicationContext per ADR 0013 and SDD-011.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.bootstrap import build_application_context
from services.dto.watcher import WatcherStatusDTO
from services.watcher import WatcherService
from tests.helpers.boundary_reflection import (
    audit_command_neutrality,
    audit_context_gateway,
    audit_dto_purity,
    audit_service_constructor_shielding,
    format_violation_diagnostic,
)


class TestJunction1ContextGateway:
    """Verifies Junction 1: ApplicationContext Gateway reflection audits."""

    def test_junction1_identifies_active_telemetry_engine_leak(self) -> None:
        """Asserts that the current build_application_context() actively flags the engine leak.

        This test serves as the active baseline benchmark proving the reflection validator
        operates correctly and will guard against future regressions.
        """
        app_ctx = build_application_context()
        violations = audit_context_gateway(app_ctx)

        # There must be exactly one violation: 'engine'
        engine_violations = [v for v in violations if v.field_or_param_name == "engine"]
        assert len(engine_violations) == 1, (
            "Expected Junction 1 to detect 'engine' leak on ApplicationContext, "
            f"found {len(engine_violations)} violations."
        )

        v = engine_violations[0]
        assert v.leaked_type_name == "TelemetryEngine"
        assert v.leaked_module_path == "domain.engine"
        assert v.junction_name == "Junction 1: Context Gateway"

        # Verify standardized diagnostic formatting
        formatted = format_violation_diagnostic(v)
        assert "ARCHITECTURAL RUNTIME BOUNDARY VIOLATION: Invariant D" in formatted
        assert "ApplicationContext.engine" in formatted
        assert "domain.engine" in formatted
        assert "Remediation:" in formatted

    def test_junction1_verifies_pure_services_pass(self) -> None:
        """Asserts that watcher_service attribute on app_ctx does not generate a violation."""
        app_ctx = build_application_context()
        violations = audit_context_gateway(app_ctx)

        watcher_violations = [v for v in violations if v.field_or_param_name == "watcher_service"]
        assert len(watcher_violations) == 0, f"watcher_service flagged unexpectedly: {watcher_violations}"


class TestJunction2QueryDTOPurity:
    """Verifies Junction 2: Query DTO Purity reflection audits."""

    def test_junction2_watcher_status_dto_is_pure(self) -> None:
        """Asserts that production WatcherStatusDTO contains zero leaked domain/adapter types."""
        dto = WatcherStatusDTO(
            is_active=True,
            journal_dir="/tmp/fake_dir",
        )
        violations = audit_dto_purity(dto)
        assert len(violations) == 0, f"WatcherStatusDTO flagged with violations: {violations}"

    def test_junction2_flags_leaked_domain_entity_in_dto(self) -> None:
        """Simulates a DTO containing a leaked domain object and asserts it is flagged."""

        @dataclass(frozen=True)
        class ImpureDTO:
            name: str
            leaked_entity: Any

        from domain.engine import TelemetryEngine

        fake_engine = TelemetryEngine(watcher=None)  # type: ignore[arg-type]
        dto = ImpureDTO(name="test", leaked_entity=fake_engine)

        violations = audit_dto_purity(dto)
        assert len(violations) == 1
        assert violations[0].leaked_type_name == "TelemetryEngine"
        assert violations[0].leaked_module_path == "domain.engine"


class TestJunction3CommandNeutrality:
    """Verifies Junction 3: Inbound Command Neutrality reflection audits."""

    def test_junction3_pure_command_passes(self) -> None:
        """Asserts that pure primitive commands pass cleanly."""

        @dataclass(frozen=True)
        class StartWatchCommand:
            journal_path: str
            ingestion_mode: str

        cmd = StartWatchCommand(journal_path="/tmp", ingestion_mode="tail")
        violations = audit_command_neutrality(cmd)
        assert len(violations) == 0

    def test_junction3_flags_framework_context_leak(self) -> None:
        """Simulates an inbound command wrapping an argparse.Namespace object."""

        @dataclass(frozen=True)
        class ContaminatedCommand:
            param: str
            framework_obj: Any

        import argparse

        cmd = ContaminatedCommand(param="run", framework_obj=argparse.Namespace())
        violations = audit_command_neutrality(cmd)
        assert len(violations) == 1
        assert violations[0].invariant_name == "Invariant C: Protocol Framework Neutrality"
        assert violations[0].leaked_type_name == "Namespace"


class TestJunction4ServiceConstructorShielding:
    """Verifies Junction 4: Service Constructor Dependency Shielding reflection audits."""

    def test_junction4_watcher_service_constructor_binds_ports_only(self) -> None:
        """Asserts that WatcherService constructor only type-hints abstract domain ports."""
        violations = audit_service_constructor_shielding(WatcherService)
        assert len(violations) == 0, f"WatcherService constructor flagged: {violations}"

    def test_junction4_flags_concrete_infrastructure_adapter_in_constructor(self) -> None:
        """Simulates a service constructor directly binding a concrete infrastructure adapter."""

        class DefectiveService:
            def __init__(self, watcher: Any) -> None:
                self.watcher = watcher

        from infrastructure.watcher.watcher import FileSystemWatcher

        # Manually annotate constructor with concrete adapter
        DefectiveService.__init__.__annotations__ = {"watcher": FileSystemWatcher}

        violations = audit_service_constructor_shielding(DefectiveService)
        assert len(violations) == 1
        assert violations[0].invariant_name == "Invariant G: Infrastructure Adapter Isolation"
        assert violations[0].leaked_type_name == "FileSystemWatcher"
        assert violations[0].leaked_module_path == "infrastructure.watcher.watcher"
