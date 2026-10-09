---
title: "Application Service Layer Scaffolding Reference"
tags: ["reference", "architecture", "ed_app", "scaffolding"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# Application Service Layer Scaffolding Reference

Technical specifications for the application service layer foundation, context composition, base protocols, and boundary contracts within `ed_app`. Governed by [ADR 0010](../../architecture/adr/0010_application_service_layer_and_boundary_contracts.md) and [SDD-008](../../architecture/designs/0008_application_service_layer_and_boundary_contracts.md).

---

## 1. Module Layout

The application service scaffolding resides within `packages/ed_app/`:

```
packages/ed_app/
├── __init__.py           # Public exports (ApplicationContext, build_application_context, ApplicationServiceError)
├── bootstrap.py          # Composition root (build_application_context, build_engine)
├── context.py            # ApplicationContext container
├── exceptions.py         # ApplicationServiceError hierarchy
├── dto/
│   ├── __init__.py       # DTO protocol export
│   └── base.py           # DataTransferObject protocol
├── services/
│   ├── __init__.py       # Service protocol export
│   └── base.py           # BaseApplicationService protocol
└── cli/
    ├── __init__.py       # CLI runner export
    └── main.py           # Smoke test CLI daemon entry point
```

---

## 2. Abstractions and Protocols

### `DataTransferObject` Protocol

Defined in `ed_app.dto.base.DataTransferObject`. A `@runtime_checkable` protocol satisfied by frozen dataclasses:

```python
@runtime_checkable
class DataTransferObject(Protocol):
    """Protocol satisfied by frozen DTO dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize DTO fields to a dictionary of primitive types."""
        ...
```

* **Contract:** Must be immutable, serializable, and decoupled from transport protocols (HTTP/FastAPI/Click).

### `BaseApplicationService` Protocol

Defined in `ed_app.services.base.BaseApplicationService`. A `@runtime_checkable` protocol satisfied by all domain application services:

```python
@runtime_checkable
class BaseApplicationService(Protocol):
    """Protocol satisfied by all application services."""

    @property
    def service_name(self) -> str:
        """Unique service identifier string."""
        ...
```

---

## 3. Application Context

Defined in `ed_app.context.ApplicationContext`:

```python
@dataclass(frozen=True)
class ApplicationContext:
    """Immutable application context holding the domain engine and registered services."""

    engine: TelemetryEngine
    services: tuple[Any, ...] = ()
```

* **Pure Scaffolding State:** In this phase, `services` defaults to an empty tuple `()`. Concrete domain services are attached during subsequent feature milestones.
* **Immutability:** Reassigning fields or mutating state raises `dataclasses.FrozenInstanceError`.

---

## 4. Composition Root

Defined in `ed_app.bootstrap`:

```python
def build_engine(journal_dir: Path | None = None) -> TelemetryEngine:
    """Instantiate concrete adapters and inject into the core domain engine."""
    ...


def build_application_context(journal_dir: Path | None = None) -> ApplicationContext:
    """Instantiate and assemble the full application context."""
    ...
```

* **Side-Effect-Free Construction:** Guaranteed zero socket binding, zero file creation, and zero background thread spawning during context construction.

---

## 5. Exception Hierarchy

Defined in `ed_app.exceptions`:

```
ApplicationServiceError (Base)
├── ServiceDependencyError (Uninitialized or unavailable dependency)
├── ServiceStateError      (Invalid operation for current lifecycle state)
└── ServicePayloadError    (Payload validation constraint violation)
```

---

## 6. Architectural Boundary Invariants

Enforced by `import-linter` in `pyproject.toml`:

| Invariant | Scope | Rule |
| :--- | :--- | :--- |
| **Invariant G** | Adapter Isolation | `ed_app.cli` and `ed_app.services` cannot directly import `ed_watcher` or `ed_egress`. Concrete adapters are isolated to `ed_app.bootstrap`. |
| **Invariant D** | Downward Dependency | Downward dependency layering enforced across `ed_app.cli` -> `ed_app.bootstrap` -> `ed_app.services` -> `ed_app.context` -> `ed_app.dto` -> `ed_app.exceptions`. |
| **Invariant C** | Protocol Neutrality | `ed_app.services` and `ed_app.dto` are forbidden from importing presentation frameworks (`argparse`, `click`, `fastapi`, `starlette`, `mcp`). |
