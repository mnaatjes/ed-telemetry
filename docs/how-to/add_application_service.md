---
title: "How to Add a Service to the Application Service Layer"
tags: ["how-to", "runbooks", "application", "services", "dto", "hexagonal"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# How to Add a Service to the Application Service Layer

This developer runbook details the canonical, step-by-step procedure for creating and integrating a new use-case service into the Application Service Layer (`packages/ed_app/services/`), strictly honoring Hexagonal Architecture boundary invariants governed by [ADR 0010](../../architecture/adr/0010_application_service_layer_and_boundary_contracts.md) and [SDD-008](../../architecture/designs/0008_application_service_layer_and_boundary_contracts.md).

---

## Prerequisites & Governing Invariants

Before authoring code, review the five mandatory architectural invariants:
1. **Invariant C (Protocol Neutrality):** Services and DTOs must never import or raise web/CLI framework types (`fastapi`, `click`, `argparse`, `mcp`, `sys.exit`).
2. **Invariant D (Downward Dependency Rule):** `ed_app.services` and `ed_app.dto` must never import driving surfaces (`ed_app.cli`, `ed_app.api`, `ed_app.mcp`).
3. **Invariant E (DTO Boundary Isolation):** Services must return pure, serializable DTOs to driving surfaces, never mutable internal domain aggregates or raw entity pointers.
4. **Invariant F (Side-Effect-Free Construction):** Constructors (`__init__`) must strictly assign dependencies without starting threads, binding sockets, or performing disk I/O.
5. **Invariant G (Infrastructure Adapter Isolation):** Services must interact with infrastructure strictly through abstract domain ports (`ed_domain.ports.WatcherPort`, `ed_domain.ports.EgressPort`), never concrete adapters (`ed_watcher`, `ed_egress`).

---

## The 6-Step Implementation Checklist

### Step 1: Declare Data Transfer Objects (`packages/ed_app/dto/`)
Create a new module under `packages/ed_app/dto/<use_case>.py`. All DTOs must be frozen dataclasses containing strictly standard library primitive types:

```python
"""packages/ed_app/dto/telemetry.py"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TelemetryStatusDTO:
    """Read-only operational status of the telemetry pipeline."""

    is_active: bool
    active_stream: str | None
    events_ingested: int
    timestamp: datetime
```

*Rule Checklist:*
* [x] Decorated with `@dataclass(frozen=True)`
* [x] Strictly standard library types (`str`, `int`, `float`, `bool`, `datetime`, `UUID`, `tuple`)
* [x] Zero imports from `ed_domain`, `ed_watcher`, or web/CLI frameworks

---

### Step 2: Declare Service Exceptions (`packages/ed_app/exceptions.py`)
Add strongly-typed application exceptions subclassing `ApplicationServiceError`:

```python
"""packages/ed_app/exceptions.py"""


class ApplicationServiceError(Exception):
    """Base exception for all application-layer failures."""


class TelemetryStreamNotReadyError(ApplicationServiceError):
    """Raised when an operation targets an uninitialized telemetry stream."""
```

---

### Step 3: Implement the Application Service (`packages/ed_app/services/`)
Create `packages/ed_app/services/<use_case>.py`. Inject domain engines, aggregates, or abstract ports via constructor:

```python
"""packages/ed_app/services/telemetry.py"""

from datetime import UTC, datetime

from ed_app.dto.telemetry import TelemetryStatusDTO
from ed_app.exceptions import TelemetryStreamNotReadyError
from ed_app.services.base import BaseApplicationService
from ed_domain.ports.watcher import WatcherPort


class TelemetryControlService(BaseApplicationService):
    """Orchestrates inbound telemetry watcher lifecycle and state queries."""

    def __init__(self, watcher: WatcherPort) -> None:
        self._watcher = watcher

    def get_status(self) -> TelemetryStatusDTO:
        """Query and return current watcher status DTO."""
        return TelemetryStatusDTO(
            is_active=self._watcher.is_active,
            active_stream=str(self._watcher.journal_dir) if self._watcher.journal_dir else None,
            events_ingested=0,
            timestamp=datetime.now(UTC),
        )

    def start_pipeline(self) -> TelemetryStatusDTO:
        """Start inbound telemetry streaming."""
        self._watcher.start()
        return self.get_status()
```

*Rule Checklist:*
* [x] Subclasses or implements `BaseApplicationService`
* [x] Accepts abstract domain ports or domain engine handles
* [x] Zero imports from `ed_watcher`, `ed_egress`, `fastapi`, or `click`
* [x] Methods return immutable DTOs or standard primitives

---

### Step 4: Register Service in `ApplicationContext` (`packages/ed_app/context.py`)
Add the typed service field to the frozen `ApplicationContext` dataclass:

```python
"""packages/ed_app/context.py"""

from dataclasses import dataclass

from ed_app.services.telemetry import TelemetryControlService
from ed_domain.engine import TelemetryEngine


@dataclass(frozen=True)
class ApplicationContext:
    """Immutable bundle of initialized application services and engine handles."""

    engine: TelemetryEngine
    telemetry_control: TelemetryControlService
```

---

### Step 5: Wire Service in the Composition Root (`packages/ed_app/bootstrap.py`)
Instantiate the service inside `build_application_context()`:

```python
"""packages/ed_app/bootstrap.py"""

from pathlib import Path

from ed_app.context import ApplicationContext
from ed_app.services.telemetry import TelemetryControlService
from ed_domain.engine import TelemetryEngine
from ed_egress.transmitter import NullTransmitter
from ed_watcher.watcher import FileSystemWatcher


def build_application_context(
    journal_dir_override: Path | None = None,
) -> ApplicationContext:
    """Instantiate ports, domain engine, and application services into a frozen context."""
    watcher = FileSystemWatcher(journal_dir=journal_dir_override)
    engine = TelemetryEngine(watcher=watcher, egress_ports=[NullTransmitter()])

    # Wire application services
    telemetry_control = TelemetryControlService(watcher=watcher)

    return ApplicationContext(
        engine=engine,
        telemetry_control=telemetry_control,
    )
```

---

### Step 6: Expose on Driving Surfaces (`cli`, `api`, `mcp`)
Driving surfaces consume the service through `ApplicationContext` with zero internal domain access:

```python
"""Example: Consuming via CLI (packages/ed_app/cli/status.py)"""

from ed_app.context import ApplicationContext


def render_status(ctx: ApplicationContext) -> int:
    status = ctx.telemetry_control.get_status()
    print(f"Telemetry Active: {status.is_active}")
    print(f"Active Stream:    {status.active_stream}")
    return 0
```

---

## Verification & Architecture Boundary Gates

Run the local verification suite to ensure all architectural invariants and formatting rules pass:

```bash
# Verify boundary invariants (Invariants C, D, G)
.venv/bin/python -m importlinter

# Full Tier 2 pipeline verification
.venv/bin/python scripts/verify.py
```
