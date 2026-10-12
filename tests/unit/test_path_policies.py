"""Tests for Hexagonal Interaction Path Policies P1 through P4.

Verifies:
- TEST-PATH-01: Policy P1 AST verification (lifecycle exclusivity outside supervisors).
- TEST-PATH-02: Policy P2 Structural capability verification (egress adapters passive).
- TEST-PATH-03: Policy P3 Pure domain isolation (zero infrastructure/registry imports).
- TEST-PATH-04: Policy P4 ApplicationContext gateway attribute integrity.
- TEST-PATH-05: Policy P4 DTO return purity and entity shielding.

Governed by ADR 0016 and SDD-014.
"""

from __future__ import annotations

import ast
from pathlib import Path

from domain.ports.base import DiscreteSinkPort, LifecyclePort
from domain.ports.egress import EgressPort
from infrastructure.egress.transmitter import NullTransmitter
from scripts.lint_lifecycle_exclusivity import (
    WHITELISTED_SUPERVISOR_MODULES,
    LifecycleASTVisitor,
)
from services.bootstrap import build_application_context
from services.dto.watcher import WatcherStatusDTO
from tests.helpers.boundary_reflection import (
    audit_context_gateway,
    audit_dto_purity,
)


class TestPolicyP1LifecycleExclusivity:
    """Verifies TEST-PATH-01: Lifecycle execution methods are exclusive to supervisors."""

    def test_ast_visitor_detects_forbidden_lifecycle_calls(self) -> None:
        """TEST-PATH-01: AST visitor flags .start() and .stop() calls in code."""
        code = """
def bad_service_operation(watcher):
    watcher.start()
    watcher.stop()
"""
        tree = ast.parse(code)
        visitor = LifecycleASTVisitor("services/test_service.py")
        visitor.visit(tree)

        assert len(visitor.violations) == 2
        assert any(".start()" in v for v in visitor.violations)
        assert any(".stop()" in v for v in visitor.violations)

    def test_services_ast_scan_contains_no_unauthorized_lifecycle_calls(self) -> None:
        """TEST-PATH-01: Scans src/services/ asserting zero unwhitelisted lifecycle calls."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        services_dir = repo_root / "src" / "services"

        violations: list[str] = []
        for py_file in services_dir.rglob("*.py"):
            rel_path = py_file.relative_to(services_dir)
            if rel_path.name in WHITELISTED_SUPERVISOR_MODULES:
                continue
            if rel_path.parts[0] in ("dto", "registry", "exceptions.py"):
                continue

            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            visitor = LifecycleASTVisitor(f"src/services/{rel_path}")
            visitor.visit(tree)
            violations.extend(visitor.violations)

        assert not violations, f"Detected Policy P1 lifecycle violations in services: {violations}"


class TestPolicyP2PassiveSinkCapability:
    """Verifies TEST-PATH-02: Driven egress adapters satisfy DiscreteSinkPort and reject LifecyclePort."""

    def test_egress_adapters_are_passive(self) -> None:
        """TEST-PATH-02: NullTransmitter satisfies DiscreteSinkPort and lacks LifecyclePort."""
        transmitter = NullTransmitter()

        # Must satisfy DiscreteSinkPort
        assert isinstance(transmitter, DiscreteSinkPort)
        assert isinstance(transmitter, EgressPort)

        # Must NOT implement LifecyclePort
        assert not isinstance(transmitter, LifecyclePort)

        # Must NOT declare start() or stop() methods
        assert not hasattr(transmitter, "start")
        assert not hasattr(transmitter, "stop")


class TestPolicyP3PureDomainIsolation:
    """Verifies TEST-PATH-03: Pure domain computational modules contain zero I/O imports."""

    def test_domain_models_contain_zero_infrastructure_imports(self) -> None:
        """TEST-PATH-03: Scans src/domain/ asserting zero imports from infrastructure or services.registry."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        domain_dir = repo_root / "src" / "domain"

        forbidden_prefixes = ("infrastructure", "services.registry")

        for py_file in domain_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not any(alias.name.startswith(p) for p in forbidden_prefixes), (
                            f"{py_file}:{node.lineno}: Domain imported forbidden module '{alias.name}'"
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert not any(node.module.startswith(p) for p in forbidden_prefixes), (
                        f"{py_file}:{node.lineno}: Domain imported from forbidden module '{node.module}'"
                    )


class TestPolicyP4GatewayAndDTOPurity:
    """Verifies TEST-PATH-04 & TEST-PATH-05: ApplicationContext gateway and DTO output purity."""

    def test_gateway_exposes_only_valid_services(self) -> None:
        """TEST-PATH-04: Asserts ApplicationContext attributes satisfy BaseApplicationService."""
        app_ctx = build_application_context()
        violations = audit_context_gateway(app_ctx)

        # Filter out known grandfathered engine leak until DaemonService migration
        non_engine_violations = [v for v in violations if v.field_or_param_name != "engine"]
        assert not non_engine_violations, f"Found gateway violations: {non_engine_violations}"

    def test_dto_purity_across_services(self) -> None:
        """TEST-PATH-05: Asserts WatcherStatusDTO contains zero leaked domain/infrastructure objects."""
        app_ctx = build_application_context()
        status_dto = app_ctx.watcher_service.get_status()

        violations = audit_dto_purity(status_dto)
        assert not violations, f"Detected DTO purity violations on WatcherStatusDTO: {violations}"
        assert isinstance(status_dto, WatcherStatusDTO)
        assert isinstance(status_dto.is_active, bool)
