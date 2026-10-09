---
title: "How to Add a Service to the Application Service Layer"
tags: ["how-to", "runbooks", "ed_app", "architecture", "services"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# How to Add a Service to the Application Service Layer

This runbook outlines the required procedure for authoring and onboarding a new domain service into `packages/ed_app/services/` within `ed-telemetry`. Governed by [ADR 0010](../../architecture/adr/0010_application_service_layer_and_boundary_contracts.md) and [SDD-008](../../architecture/designs/0008_application_service_layer_and_boundary_contracts.md).

---

## Prerequisites

Before implementing a service in the application service layer:

1. The underlying domain business models and parsing logic must already exist in `packages/ed_domain/` (governed by [ADR 0001](../../architecture/adr/0001_domain_model_and_core_abstractions.md)).
2. Any required inbound data sources (e.g. `ed_watcher`) or outbound sinks (e.g. `ed_egress`) must implement the core domain port contracts in `ed_domain.ports`.

---

## Standard Operating Procedure

Follow this 6-step checklist sequentially:

### Step 1: Define Boundary Data Transfer Objects (DTOs)

Create or update DTO dataclasses in `packages/ed_app/dto/`:

1. Mark every DTO with `@dataclass(frozen=True)` to guarantee immutability across concurrency boundaries.
2. Implement the `DataTransferObject` protocol (`to_dict(self) -> dict[str, Any]`).
3. Ensure the DTO only uses primitive Python types (`str`, `int`, `float`, `bool`, `dict`, `list`, `tuple`, `None`).
4. **Never** import presentation frameworks (`click`, `fastapi`, `mcp`, `argparse`) inside `ed_app/dto/` (Invariant C).

```python
# packages/ed_app/dto/example.py
from dataclasses import dataclass
from typing import Any

from ed_app.dto.base import DataTransferObject


@dataclass(frozen=True)
class ExampleDTO:
    id: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status}
```

---

### Step 2: Define Service-Specific Domain Exceptions

If your service introduces operational failure modes:

1. Subclass from `ApplicationServiceError` in `packages/ed_app/exceptions.py` (or a service-specific submodule inheriting from it).
2. Choose the appropriate specialization:
   - `ServiceDependencyError`: Raised when downstream engine or port dependencies are missing or failing.
   - `ServiceStateError`: Raised when queried before the service has reached a valid lifecycle state.
   - `ServicePayloadError`: Raised when invalid queries or arguments are passed.

---

### Step 3: Implement the Service Class

Create your service in `packages/ed_app/services/<service_name>.py`:

1. Satisfy the `BaseApplicationService` protocol by exposing a unique `service_name: str` property.
2. Invert dependencies: take domain engine, repositories, or port dependencies in the `__init__` constructor.
3. Accept and return primitive values or frozen DTOs from `ed_app.dto`.
4. **Forbidden:** Do not import `ed_watcher`, `ed_egress`, `ed_app.cli`, `ed_app.api`, or `ed_app.mcp` (Invariants G and D).

```python
# packages/ed_app/services/example.py
from ed_app.dto.example import ExampleDTO
from ed_app.exceptions import ServiceStateError
from ed_app.services.base import BaseApplicationService
from ed_domain.engine import TelemetryEngine


class ExampleService(BaseApplicationService):
    def __init__(self, engine: TelemetryEngine) -> None:
        self._engine = engine

    @property
    def service_name(self) -> str:
        return "example_service"

    def get_status(self) -> ExampleDTO:
        if not self._engine.is_running:
            raise ServiceStateError("Engine is not running")
        return ExampleDTO(id="srv-1", status="active")
```

---

### Step 4: Register in Application Context and Composition Root

1. Update `packages/ed_app/context.py` to type the service field:
   ```python
   @dataclass(frozen=True)
   class ApplicationContext:
       engine: TelemetryEngine
       example_service: ExampleService
       services: tuple[Any, ...] = ()
   ```
2. Update `packages/ed_app/bootstrap.py` in `build_application_context()` to instantiate and inject the service:
   ```python
   def build_application_context(journal_dir: Path | None = None) -> ApplicationContext:
       engine = build_engine(journal_dir=journal_dir)
       example_service = ExampleService(engine=engine)
       return ApplicationContext(
           engine=engine,
           example_service=example_service,
           services=(example_service,),
       )
   ```

---

### Step 5: Author Unit Tests and Side-Effect-Freedom Verification

Create unit tests under `tests/unit/test_<service_name>_service.py`:

1. Verify constructor does not spawn threads or open file handles.
2. Verify methods return frozen DTOs satisfying `isinstance(result, DataTransferObject)`.
3. Verify failure paths raise the expected `ApplicationServiceError` subclasses.

---

### Step 6: Verify Boundary Invariants and Linters

Run the repository verification suite to ensure no architectural boundaries were breached:

```bash
# 1. Run type and lint checks
.venv/bin/ruff check packages tests
.venv/bin/ruff format --check packages tests
.venv/bin/mypy

# 2. Run import boundary linter (Invariants G, D, C)
.venv/bin/lint-imports

# 3. Run full verification suite
.venv/bin/python3 scripts/verify.py

# 4. Verify cross-platform compatibility under Wine
./scripts/run_wine_tests.sh
```
