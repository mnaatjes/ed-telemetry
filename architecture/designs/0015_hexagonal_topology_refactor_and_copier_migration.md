---
title: "SDD-015: Hexagonal Topology Modernization, Copier Scaffolding, and Use Case Refactor"
status: "proposed"
authors: ["@mnaatjes"]
reviewers: ["Systems Engineering Team"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
related_adrs: ["architecture/adr/0017_migration_to_standard_hexagonal_template_and_service_retirement.md"]
related_rfcs: []
tags: ["architecture", "sdd", "hexagonal", "copier", "use-cases", "ports-and-adapters", "refactoring"]
---

# SDD-015: Hexagonal Topology Modernization, Copier Scaffolding, and Use Case Refactor

This Software Design Document specifies the concrete technical implementation for refactoring `ed-telemetry` into the standardized single-root hexagonal topology mandated by `python-hexagonal-template` and governed by [ADR 0017](../adr/0017_migration_to_standard_hexagonal_template_and_service_retirement.md).

---

## 1. System Overview & Target Topology

The refactored system adopts the single-root Python package layout under `src/ed_telemetry/`. All legacy multi-root packages (`domain`, `services`, `infrastructure`, `interfaces`) are reorganized strictly within the standardized layers:

```
src/ed_telemetry/
├── __init__.py
├── bootstrap/
│   ├── __init__.py
│   └── container.py                  # Pure composition root / DI factory
├── core/
│   ├── __init__.py
│   ├── domain/                       # Pure domain entities, value objects, domain errors
│   │   ├── __init__.py
│   │   ├── exceptions.py             # DomainError hierarchy
│   │   └── models.py                 # Self-validating immutable domain models
│   ├── ports/                        # Boundary protocols & immutable DTOs
│   │   ├── __init__.py
│   │   ├── base.py                   # Port, DrivingPort, DrivenPort marker protocols
│   │   ├── driving/                  # Abstract interfaces implemented by use cases
│   │   │   ├── __init__.py
│   │   │   └── telemetry_port.py     # WatchTelemetryPort, ProcessSnapshotPort & DTOs
│   │   └── driven/                   # Abstract interfaces implemented by outer adapters
│   │       ├── __init__.py
│   │       ├── lifecycle_port.py     # Worker lifecycle management (start/stop)
│   │       ├── discrete_sink_port.py # Outbound point-in-time transmission sink
│   │       ├── stream_source_port.py # Inbound event registration
│   │       ├── watcher_port.py       # WatcherPort interface
│   │       └── egress_port.py        # EgressPort interface
│   └── use_cases/                    # Stateless interactors orchestrating domain & driven ports
│       ├── __init__.py
│       ├── watch_telemetry.py        # WatchTelemetryUseCase
│       └── process_snapshot.py       # ProcessSnapshotUseCase
└── adapters/
    ├── __init__.py
    ├── driving/                      # Inbound transport controllers
    │   ├── __init__.py
    │   └── cli/                      # CLI entrypoint & subcommands
    └── driven/                       # Outbound infrastructure implementations
        ├── __init__.py
        ├── egress/                   # Egress adapters (NullTransmitter, network sinks)
        └── watcher/                  # Filesystem watcher adapter
            ├── discovery/            # OS path discovery strategies
            ├── engine/               # StreamContext, Tailer, Reactor, Envelopes
            ├── selector.py           # Journal candidate sorting
            ├── snapshots/            # Snapshot identifier & registry
            └── file_system_watcher.py# FileSystemWatcher adapter
```

---

## 2. Port Architecture & Genealogy Redesign

In compliance with `HEXA-TRUTH-03`, `HEXA-TRUTH-20`, and `HEXA-TRUTH-21`, the port hierarchy is redesigned into strictly segregated directional trees.

### 2.1 Root Marker Protocols (`core/ports/base.py`)

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class Port(Protocol):
    """Root marker protocol for all boundary interfaces."""


@runtime_checkable
class DrivingPort(Port, Protocol):
    """Marker protocol for driving ports implemented strictly by use cases."""


@runtime_checkable
class DrivenPort(Port, Protocol):
    """Marker protocol for driven ports implemented strictly by outer adapters."""
```

### 2.2 Driven Capabilities and Port Interfaces (`core/ports/driven/`)

1. **`LifecyclePort`**:
   ```python
   @runtime_checkable
   class LifecyclePort(DrivenPort, Protocol):
       def start(self) -> None: ...
       def stop(self) -> None: ...
       @property
       def is_active(self) -> bool: ...
   ```
2. **`StreamSourcePort`**:
   ```python
   @runtime_checkable
   class StreamSourcePort(DrivenPort, Protocol):
       def register_event_handler(self, handler: IngestionEventHandler) -> None: ...
       def register_audit_handler(self, handler: AuditEventHandler) -> None: ...
   ```
3. **`DiscreteSinkPort`**:
   ```python
   @runtime_checkable
   class DiscreteSinkPort(DrivenPort, Protocol):
       def send(self, payload: Mapping[str, Any]) -> None: ...
   ```
4. **`WatcherPort`**:
   Inherits `DrivenPort`, `LifecyclePort`, and `StreamSourcePort`.
5. **`EgressPort`**:
   Inherits `DrivenPort` and `DiscreteSinkPort`.

### 2.3 Driving Ports and DTO Contracts (`core/ports/driving/`)

Driving ports define operations triggered by driving surfaces (CLI, MCP, API). In compliance with `HEXA-TRUTH-25` and `HEXA-TRUTH-28`:
- Port names represent business intention, not persistence CRUD.
- Method parameters and return values are pure primitives or frozen dataclasses.

```python
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class WatcherStatusDTO:
    is_active: bool
    active_journal: str | None
    monitored_directory: str | None


@runtime_checkable
class WatchTelemetryPort(DrivingPort, Protocol):
    def get_status(self) -> WatcherStatusDTO: ...
    def start_monitoring(self) -> None: ...
    def stop_monitoring(self) -> None: ...
```

---

## 3. Application Use Cases (`core/use_cases/`)

Application services (`src/services/`) are eliminated. Business capabilities are encapsulated in isolated, stateless interactors matching `^[A-Z][a-zA-Z0-9]+UseCase$` (`HEXA-TRUTH-11, 14`):

### 3.1 `WatchTelemetryUseCase`
- **Implements**: `WatchTelemetryPort`
- **Dependencies (Injected via `__init__`)**: `WatcherPort`, `EgressPort`
- **Responsibilities**:
  - Validates and coordinates start/stop operations against the injected driven `WatcherPort`.
  - Dispatches normalized event streams to the injected driven `EgressPort`.
  - Returns immutable `WatcherStatusDTO` snapshots without exposing concrete adapter references.

### 3.2 Extensibility for Future Driving Adapters (CLI, MCP, API)
Because use cases depend strictly on driven ports and expose pure driving ports returning frozen DTOs:
- **CLI Adapter (`adapters/driving/cli/`)**: Calls `WatchTelemetryUseCase.get_status()` or `start_monitoring()`.
- **MCP Server Adapter (`adapters/driving/mcp/`)**: Can expose tools (`get_telemetry_status`, `stream_telemetry`) calling the same use cases.
- **REST / WebSocket API (`adapters/driving/api/`)**: Can map HTTP/WebSocket routes directly into use case methods.

---

## 4. Test Double Parity Architecture (`HEXA-TRUTH-27`)

Every driven port defined in `core/ports/driven/` has an in-memory double in `tests/doubles/`:

1. **`FakeWatcherAdapter` (`tests/doubles/fake_watcher_adapter.py`)**:
   - Satisfies `WatcherPort` (`LifecyclePort` + `StreamSourcePort`).
   - Simulates journal events, allows triggering test file ingestion events, and records `.start()` / `.stop()` calls without spawning OS threads.
2. **`FakeEgressAdapter` (`tests/doubles/fake_egress_adapter.py`)**:
   - Satisfies `EgressPort` (`DiscreteSinkPort`).
   - Captures transmitted payloads in an internal list for test assertions.

---

## 5. Composition Root & Dependency Injection (`bootstrap/container.py`)

In compliance with `HEXA-TRUTH-19`, the composition root is isolated under `bootstrap/container.py`. It is the sole structural authority permitted to import both concrete adapters and use cases:

```python
from dataclasses import dataclass
from pathlib import Path
from ed_telemetry.adapters.driven.egress.null_transmitter import NullTransmitter
from ed_telemetry.adapters.driven.watcher.file_system_watcher import FileSystemWatcher
from ed_telemetry.core.use_cases.watch_telemetry import WatchTelemetryUseCase


@dataclass(frozen=True, slots=True)
class Container:
    watch_telemetry_use_case: WatchTelemetryUseCase


def build_container(
    journal_dir: Path | None = None,
    poll_interval: float | None = None,
) -> Container:
    """Build and wire production container graph."""
    watcher = FileSystemWatcher(journal_dir=journal_dir, poll_interval=poll_interval)
    egress = NullTransmitter()
    use_case = WatchTelemetryUseCase(watcher=watcher, egress=egress)
    return Container(watch_telemetry_use_case=use_case)
```

---

## 6. Verification Pipeline & CI Matrix Architecture

The unified quality gate pipeline is defined as:

1. **Local Pre-commit (`.pre-commit-config.yaml`)**:
   - `check-added-large-files` (maxkb: 500)
   - `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`
   - `ruff` (lint --fix) & `ruff-format`
2. **Automated Verification Script (`scripts/verify.py`)**:
   - Pre-commit check (`pre-commit run --all-files`)
   - Import Linter contracts (`lint-imports` against Jinja-templated contracts)
   - Static type analysis (`mypy src/`)
   - Boundary tests and unit tests (`pytest tests/`)
3. **GitHub Actions CI (`.github/workflows/ci.yml`)**:
   - Matrix across Ubuntu and Windows (`ubuntu-latest`, `windows-latest`)
   - Python versions: `3.12`, `3.13`
   - Astral `uv` setup, virtual environment sync, and execution of `scripts/verify.py`

---

## 7. Phased Implementation Roadmap

* **Step 1: Branch Creation & Preparation**
  - Create feature branch `refactor/hexagonal-template-alignment`.
  - Validate clean working tree.
* **Step 2: Source Tree Restructuring**
  - Scaffold `src/ed_telemetry/{bootstrap,core,adapters}`.
  - Relocate domain modules, port interfaces, and driven adapters.
  - Remove deprecated `src/services/` and `src/services/registry/`.
* **Step 3: Port Hierarchy & Use Case Implementation**
  - Implement `Port`, `DrivingPort`, `DrivenPort` hierarchy.
  - Implement `WatchTelemetryUseCase` and `ProcessSnapshotUseCase`.
  - Implement `bootstrap/container.py`.
  - Implement test doubles `FakeWatcherAdapter` and `FakeEgressAdapter`.
* **Step 4: Copier Application**
  - Apply `python-hexagonal-template` configuration (`pyproject.toml`, `.importlinter`, `tests/architecture/test_boundaries.py`, `scripts/verify.py`).
* **Step 5: Test Suite Migration & Verification**
  - Relocate 67 retained unit tests into `tests/unit/adapters/` and `tests/unit/core/`.
  - Implement unit tests for use cases and container.
  - Execute full test suite and boundary verification via `scripts/verify.py`.
