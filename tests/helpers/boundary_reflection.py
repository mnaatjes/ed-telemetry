"""Runtime Reflection Boundary Validator Harness.

Audits runtime object graphs across architectural boundary junctions to eliminate
transitive object tunneling (bypassing layer walls via attribute traversal).
Governed by ADR 0013 and SDD-011.
"""

from __future__ import annotations

import dataclasses
import datetime
import inspect
from dataclasses import dataclass
from typing import Any, get_type_hints

from services.base import BaseApplicationService


@dataclass(frozen=True)
class BoundaryViolation:
    """Encapsulates a single detected runtime boundary or object-tunneling violation."""

    invariant_name: str
    junction_name: str
    source_layer: str
    target_layer: str
    enclosing_container: str
    field_or_param_name: str
    leaked_type_name: str
    leaked_module_path: str
    policy_violation: str
    remediation_action: str


def format_violation_diagnostic(v: BoundaryViolation) -> str:
    """Format a BoundaryViolation into the standardized human-readable ADR 0013 template."""
    return (
        f"\n{'=' * 80}\n"
        f"ARCHITECTURAL RUNTIME BOUNDARY VIOLATION: {v.invariant_name}\n"
        f"{'=' * 80}\n"
        f"Junction:     {v.junction_name} ({v.source_layer} -> {v.target_layer})\n"
        f"Location:     {v.enclosing_container}.{v.field_or_param_name}\n"
        f"Leaked Type:  {v.leaked_type_name}\n"
        f"Module Path:  {v.leaked_module_path}\n"
        f"Severity:     CRITICAL (Object Tunneling Detected)\n\n"
        f"Policy Violation:\n"
        f"  {v.policy_violation}\n\n"
        f"Remediation:\n"
        f"  {v.remediation_action}\n"
        f"{'=' * 80}\n"
    )


def audit_context_gateway(app_ctx: Any) -> list[BoundaryViolation]:
    """Audit Junction 1: ApplicationContext Gateway (Services -> Interfaces).

    Verifies that every exposed attribute on ApplicationContext implements
    BaseApplicationService or is an empty/primitive container. Flags any attribute
    whose concrete instance or module originates from domain.* or infrastructure.*.
    """
    violations: list[BoundaryViolation] = []
    container_name = type(app_ctx).__name__

    if not dataclasses.is_dataclass(app_ctx):
        violations.append(
            BoundaryViolation(
                invariant_name="Invariant D: ApplicationContext Structural Integrity",
                junction_name="Junction 1: Context Gateway",
                source_layer="src/services/",
                target_layer="src/interfaces/",
                enclosing_container=container_name,
                field_or_param_name="self",
                leaked_type_name=type(app_ctx).__name__,
                leaked_module_path=type(app_ctx).__module__,
                policy_violation="ApplicationContext must be an immutable frozen dataclass.",
                remediation_action="Decorate ApplicationContext with @dataclass(frozen=True).",
            )
        )
        return violations

    for field in dataclasses.fields(app_ctx):
        val = getattr(app_ctx, field.name)
        val_type = type(val)
        val_module = val_type.__module__

        # Permit tuple of services or primitive collections if empty or all elements are services
        if field.name == "services" and isinstance(val, tuple):
            for idx, item in enumerate(val):
                if not isinstance(item, BaseApplicationService):
                    violations.append(
                        BoundaryViolation(
                            invariant_name="Invariant D: Downward Layering",
                            junction_name="Junction 1: Context Gateway",
                            source_layer="src/services/",
                            target_layer="src/interfaces/",
                            enclosing_container=container_name,
                            field_or_param_name=f"services[{idx}]",
                            leaked_type_name=type(item).__name__,
                            leaked_module_path=type(item).__module__,
                            policy_violation=(
                                "Items registered in 'services' tuple must implement BaseApplicationService."
                            ),
                            remediation_action=(
                                "Ensure all registered services satisfy BaseApplicationService protocol."
                            ),
                        )
                    )
            continue

        # Check for forbidden module leakage
        is_domain = val_module.startswith("domain")
        is_infrastructure = val_module.startswith("infrastructure")
        is_sdk = val_module.startswith("sdk")

        if is_domain or is_infrastructure or is_sdk:
            layer = "domain" if is_domain else ("infrastructure" if is_infrastructure else "sdk")
            violations.append(
                BoundaryViolation(
                    invariant_name="Invariant D: Downward Layering" if is_domain else "Invariant G: Adapter Isolation",
                    junction_name="Junction 1: Context Gateway",
                    source_layer="src/services/",
                    target_layer="src/interfaces/",
                    enclosing_container=container_name,
                    field_or_param_name=field.name,
                    leaked_type_name=val_type.__name__,
                    leaked_module_path=val_module,
                    policy_violation=(
                        f"ApplicationContext is strictly an application service container. "
                        f"Exposing raw {layer} objects ('{val_module}') directly to driving surfaces "
                        f"allows interfaces to bypass the Application Service Layer."
                    ),
                    remediation_action=(
                        f"Remove '{field.name}' from ApplicationContext. "
                        f"Encapsulate {val_type.__name__} capabilities inside an Application Service "
                        "in 'src/services/'."
                    ),
                )
            )
        elif not isinstance(val, BaseApplicationService):
            violations.append(
                BoundaryViolation(
                    invariant_name="Invariant D: Downward Layering",
                    junction_name="Junction 1: Context Gateway",
                    source_layer="src/services/",
                    target_layer="src/interfaces/",
                    enclosing_container=container_name,
                    field_or_param_name=field.name,
                    leaked_type_name=val_type.__name__,
                    leaked_module_path=val_module,
                    policy_violation=(
                        "Every operational service attribute on ApplicationContext must implement "
                        "BaseApplicationService."
                    ),
                    remediation_action=f"Ensure '{val_type.__name__}' satisfies the BaseApplicationService protocol.",
                )
            )

    return violations


ALLOWED_PRIMITIVE_TYPES = (
    int,
    float,
    str,
    bool,
    bytes,
    type(None),
    datetime.datetime,
    datetime.date,
    datetime.time,
)


def audit_dto_purity(dto_instance: Any, enclosing_path: str = "") -> list[BoundaryViolation]:
    """Audit Junction 2: Query DTO Purity (Services -> Interfaces).

    Recursively inspects dataclass fields of DTO instances to ensure that all payload values
    are pure primitives, dates, or nested frozen DTOs. Forbids any type from domain.* or infrastructure.*.
    """
    violations: list[BoundaryViolation] = []
    dto_cls = type(dto_instance)
    container_name = enclosing_path or dto_cls.__name__

    if not dataclasses.is_dataclass(dto_instance):
        violations.append(
            BoundaryViolation(
                invariant_name="Invariant E: DataTransferObject Standard",
                junction_name="Junction 2: Query DTO Purity",
                source_layer="src/services/",
                target_layer="src/interfaces/",
                enclosing_container=container_name,
                field_or_param_name="self",
                leaked_type_name=dto_cls.__name__,
                leaked_module_path=dto_cls.__module__,
                policy_violation="DataTransferObject must be an immutable frozen dataclass.",
                remediation_action="Decorate DTO with @dataclass(frozen=True).",
            )
        )
        return violations

    for field in dataclasses.fields(dto_instance):
        val = getattr(dto_instance, field.name)
        field_loc = f"{container_name}.{field.name}"
        violations.extend(_audit_dto_value(val, field_loc, field.name))

    return violations


def _audit_dto_value(val: Any, field_loc: str, field_name: str) -> list[BoundaryViolation]:
    violations: list[BoundaryViolation] = []
    if isinstance(val, ALLOWED_PRIMITIVE_TYPES):
        return violations

    val_type = type(val)
    val_module = val_type.__module__

    if val_module.startswith("domain") or val_module.startswith("infrastructure") or val_module.startswith("sdk"):
        layer = "domain" if val_module.startswith("domain") else "infrastructure"
        violations.append(
            BoundaryViolation(
                invariant_name="Invariant E: DTO Boundary Isolation",
                junction_name="Junction 2: Query DTO Purity",
                source_layer="src/services/",
                target_layer="src/interfaces/",
                enclosing_container=field_loc,
                field_or_param_name=field_name,
                leaked_type_name=val_type.__name__,
                leaked_module_path=val_module,
                policy_violation=(
                    f"DTO field contains leaked {layer} object ('{val_module}.{val_type.__name__}'). "
                    f"DTOs must consist solely of primitive Python types or nested frozen DTOs."
                ),
                remediation_action=(
                    f"Serialize {val_type.__name__} into primitive types (dict, str, int, etc.) inside the DTO."
                ),
            )
        )
        return violations

    if dataclasses.is_dataclass(val):
        violations.extend(audit_dto_purity(val, enclosing_path=field_loc))
    elif isinstance(val, (list, tuple, set)):
        for idx, item in enumerate(val):
            violations.extend(_audit_dto_value(item, f"{field_loc}[{idx}]", field_name))
    elif isinstance(val, dict):
        for k, v in val.items():
            violations.extend(_audit_dto_value(k, f"{field_loc}.keys[{k}]", field_name))
            violations.extend(_audit_dto_value(v, f"{field_loc}[{k}]", field_name))
    else:
        # Non-primitive, non-dataclass custom object
        violations.append(
            BoundaryViolation(
                invariant_name="Invariant E: DTO Boundary Isolation",
                junction_name="Junction 2: Query DTO Purity",
                source_layer="src/services/",
                target_layer="src/interfaces/",
                enclosing_container=field_loc,
                field_or_param_name=field_name,
                leaked_type_name=val_type.__name__,
                leaked_module_path=val_module,
                policy_violation=f"DTO contains non-primitive complex type '{val_type.__name__}'.",
                remediation_action="Convert field to primitive type (str, int, float, bool, None, dict, list).",
            )
        )

    return violations


FORBIDDEN_FRAMEWORK_MODULES = ("click", "argparse", "fastapi", "starlette", "mcp")


def audit_command_neutrality(command_instance: Any) -> list[BoundaryViolation]:
    """Audit Junction 3: Inbound Command Neutrality (Interfaces -> Services).

    Ensures inbound command parameters do not pass UI/CLI/Web framework context objects.
    """
    violations: list[BoundaryViolation] = []
    cmd_cls = type(command_instance)
    container_name = cmd_cls.__name__

    if not dataclasses.is_dataclass(command_instance):
        return violations

    for field in dataclasses.fields(command_instance):
        val = getattr(command_instance, field.name)
        val_type = type(val)
        val_module = val_type.__module__

        for framework in FORBIDDEN_FRAMEWORK_MODULES:
            if val_module.startswith(framework):
                violations.append(
                    BoundaryViolation(
                        invariant_name="Invariant C: Protocol Framework Neutrality",
                        junction_name="Junction 3: Inbound Command Neutrality",
                        source_layer="src/interfaces/",
                        target_layer="src/services/",
                        enclosing_container=container_name,
                        field_or_param_name=field.name,
                        leaked_type_name=val_type.__name__,
                        leaked_module_path=val_module,
                        policy_violation=(
                            f"Command object passed framework context '{framework}' into Application Service Layer."
                        ),
                        remediation_action=(
                            f"Extract required data from '{val_type.__name__}' inside the interface layer "
                            f"and pass pure primitives or value objects in the command."
                        ),
                    )
                )

    return violations


def audit_service_constructor_shielding(service_cls: type) -> list[BoundaryViolation]:
    """Audit Junction 4: Service Constructor Dependency Shielding.

    Inspects service constructor signatures to ensure dependencies bind to
    abstract domain ports (domain.ports.*) and never concrete infrastructure.* adapters.
    """
    violations: list[BoundaryViolation] = []
    sig = inspect.signature(service_cls.__init__)
    hints = get_type_hints(service_cls.__init__)

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "args", "kwargs"):
            continue

        annotation = hints.get(param_name, param.annotation)
        ann_module = getattr(annotation, "__module__", "")

        if ann_module.startswith("infrastructure"):
            violations.append(
                BoundaryViolation(
                    invariant_name="Invariant G: Infrastructure Adapter Isolation",
                    junction_name="Junction 4: Service Constructor Shielding",
                    source_layer="src/infrastructure/",
                    target_layer="src/services/",
                    enclosing_container=service_cls.__name__,
                    field_or_param_name=param_name,
                    leaked_type_name=getattr(annotation, "__name__", str(annotation)),
                    leaked_module_path=ann_module,
                    policy_violation=(
                        f"Service constructor accepts concrete infrastructure adapter '{ann_module}'. "
                        f"Application services must depend exclusively on abstract domain ports."
                    ),
                    remediation_action=(
                        f"Change constructor parameter '{param_name}' type hint to an "
                        "abstract Protocol in 'domain.ports'."
                    ),
                )
            )

    return violations
