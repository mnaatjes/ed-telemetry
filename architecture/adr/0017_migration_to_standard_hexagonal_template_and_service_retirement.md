---
title: "ADR 0017: Migration to Standard Hexagonal Template, Topology Modernization, and Service Layer Retirement"
status: "proposed"
date: "2026-10-25"
tags: ["architecture", "adr", "hexagonal", "ports-and-adapters", "copier", "template", "refactoring"]
---

# ADR 0017: Migration to Standard Hexagonal Template, Topology Modernization, and Service Layer Retirement

## 1. Context and Problem Statement

`ed-telemetry` was initially developed using a bespoke multi-root layout under `src/` (`src/domain/`, `src/services/`, `src/infrastructure/`, `src/interfaces/`, `src/sdk/`). This layout relied on a custom dynamic registry (`src/services/registry/`), an `ApplicationContext` container (`src/services/context.py`), and bespoke AST linters (`scripts/lint_lifecycle_exclusivity.py`) and reflection audits (`tests/helpers/boundary_reflection.py`) to enforce boundary isolation.

The organization has established a unified downstream service standard via [python-hexagonal-template](https://github.com/mnaatjes/python-hexagonal-template), which defines:
1. **A Single-Root Topology:** `src/{{package_name}}/{core/{domain,ports/{driving,driven},use_cases},adapters/{driving,driven},bootstrap}`.
2. **28 Hexagonal Truth Invariants (`HEXA-TRUTH-01` to `HEXA-TRUTH-28`):** Comprehensive architectural rules covering domain purity, directional port integrity, immutable frozen DTO boundaries, technology-agnostic nomenclature, test double parity, and composition root isolation.
3. **Automated Machine Enforcement:** An automated suite of AST and architectural compliance tests in `tests/architecture/test_boundaries.py`, `.importlinter.jinja`, and deterministic verification via `scripts/verify.py` and Astral `uv`.

The legacy multi-root architecture in `ed-telemetry` conflicts directly with this template standard:
* Multi-root packages break standard package packaging and single-package import boundary contracts.
* Port interfaces in `domain/ports/` lack explicit directional classification (`DrivingPort` vs. `DrivenPort`) and dual-adapter in-memory test doubles.
* The bespoke `services/` and `services/registry/` layers introduce runtime reflection complexity instead of static dependency injection via an isolated composition root (`bootstrap/container.py`).

We must establish a clean architectural decision to align `ed-telemetry` with `python-hexagonal-template` by retiring obsolete layers and adopting the standardized single-root hexagonal topology.

---

## 2. Decision Drivers

* **Ecosystem Alignment:** Bring `ed-telemetry` into strict compliance with `python-hexagonal-template` and its 28 Hexagonal Truths.
* **Simplification & Decoupling:** Eliminate complex, bespoke dynamic adapter registries and runtime reflection audits in favor of static type checking, pure dependency injection, and AST boundary testing.
* **Preservation of Core Assets:** Retain and isolate all battle-tested filesystem discovery, journal selection, snapshot identification, and streaming reactor infrastructure.
* **Standardized Composition Root:** Replace mutable `ApplicationContext` and ad-hoc bootstrap scripts with a pure, immutable composition root (`bootstrap/container.py`).
* **Offline Testability:** Guarantee offline testability via in-memory test doubles (`tests/doubles/`) matching all driven ports.
* **Multi-Interface Readiness:** Structure ports and use cases to seamlessly accommodate upcoming Driving Adapters (CLI, MCP server, REST API).

---

## 3. Decision Outcome

Chosen Option: **Execute a structural refactor of `ed-telemetry` to migrate into the standard single-root topology `src/ed_telemetry/`, retire `src/services/` and `src/services/registry/`, adopt directional ports and Use Cases, and merge the canonical scaffolding from `python-hexagonal-template` using Copier.**

---

## 4. Retained vs. Discarded Architecture Components

### 4.1 Retained Ports and Adapters Mapping

All domain entities and proven infrastructure adapters are retained and mapped into the single-root `src/ed_telemetry/` package:

| Legacy Component (`ed-telemetry`) | Legacy Role | Target Hexagonal Location (`src/ed_telemetry/`) | Target Role & Archetype | Governing Invariants |
| :--- | :--- | :--- | :--- | :--- |
| `domain.ports.base.Port` | Marker Protocol | `core/ports/base.py:Port` | Base Marker Protocol | `HEXA-TRUTH-03` |
| `domain.ports.base.LifecyclePort` | Capability Protocol | `core/ports/driven/lifecycle_port.py:LifecyclePort` | Driven Capability Protocol (inherits `DrivenPort`) | `HEXA-TRUTH-03, 21` |
| `domain.ports.base.DiscreteSinkPort` | Capability Protocol | `core/ports/driven/discrete_sink_port.py:DiscreteSinkPort` | Driven Capability Protocol (inherits `DrivenPort`) | `HEXA-TRUTH-03, 21` |
| `domain.ports.base.StreamSourcePort` | Capability Protocol | `core/ports/driven/stream_source_port.py:StreamSourcePort` | Driven Capability Protocol (inherits `DrivenPort`) | `HEXA-TRUTH-03, 21` |
| `domain.ports.watcher.WatcherPort` | Composite Driven Port | `core/ports/driven/watcher_port.py:WatcherPort` | Inbound Telemetry Driven Port (inherits `DrivenPort`) | `HEXA-TRUTH-03, 17, 21` |
| `domain.ports.egress.EgressPort` | Driven Port (Sink) | `core/ports/driven/egress_port.py:EgressPort` | Outbound Egress Driven Port (inherits `DrivenPort`) | `HEXA-TRUTH-03, 17, 21` |
| `infrastructure.watcher.watcher.FileSystemWatcher` | Driven Adapter | `adapters/driven/watcher/file_system_watcher.py` | Concrete Filesystem Watcher Adapter | `HEXA-TRUTH-02, 21, 23` |
| `infrastructure.watcher.discovery.*` | Subsystem / Engine | `adapters/driven/watcher/discovery/*` | OS Path Discovery Engine | Adapter Internal |
| `infrastructure.watcher.engine.*` | Subsystem / Engine | `adapters/driven/watcher/engine/*` | Ingestion & Reactive Reactor Engine | Adapter Internal |
| `infrastructure.watcher.selector.*` | Subsystem / Engine | `adapters/driven/watcher/selector.py` | Active Journal Candidate Selector | Adapter Internal |
| `infrastructure.watcher.snapshots.*` | Subsystem / Engine | `adapters/driven/watcher/snapshots/*` | Snapshot Catalog & Identifier | Adapter Internal |
| `infrastructure.egress.transmitter.NullTransmitter` | Driven Adapter | `adapters/driven/egress/null_transmitter.py` | In-Memory Outbound Null Egress Adapter | `HEXA-TRUTH-02, 21` |
| *New Requirement* | In-Memory Double | `tests/doubles/fake_watcher_adapter.py` | Test Double (`FakeWatcherAdapter`) | `HEXA-TRUTH-27` |
| *New Requirement* | In-Memory Double | `tests/doubles/fake_egress_adapter.py` | Test Double (`FakeEgressAdapter`) | `HEXA-TRUTH-27` |
| `interfaces.cli` | Driving Adapter | `adapters/driving/cli/*` | CLI Interface Adapter | `HEXA-TRUTH-02, 20` |
| *New Requirement* | Use Case Interactor | `core/use_cases/get_watcher_status.py` | Status Query Use Case (`GetWatcherStatusUseCase`) | `HEXA-TRUTH-11, 14, 20` |
| *New Requirement* | Use Case Interactor | `core/use_cases/process_telemetry_stream.py` | Continuous Stream Interactor (`ProcessTelemetryStreamUseCase`) | `HEXA-TRUTH-11, 14, 20` |
| *New Requirement* | Use Case Interactor | `core/use_cases/sync_journal_snapshot.py` | Point-in-time Sync Interactor (`SyncJournalSnapshotUseCase`) | `HEXA-TRUTH-11, 14, 20` |

### 4.2 Boundary Data Transfer Object (DTO) Architecture & Inventory

In strict accordance with `HEXA-TRUTH-04` (DTO & Anti-Tunneling Boundary Purity) and `HEXA-TRUTH-28` (DTO Immutability & Structural Purity):
* DTOs are co-located strictly inside `core/ports/driving/` or `core/ports/driven/`. They are strictly forbidden from `core/domain/` or `adapters/`.
* All DTOs must be decorated with `@dataclass(frozen=True, slots=True)` and inherit from marker protocol `DataTransferObject`.
* DTO field types must be restricted strictly to primitives (`str`, `int`, `float`, `bool`, `bytes`), `datetime`, `UUID`, `Path`, frozen DTOs, tuples, and frozensets. Mutable collections (`list`, `dict`, `set`) and framework/ORM models are strictly forbidden.

To satisfy the retained ports and adapters in `ed-telemetry`, the following DTOs are established:

| Target DTO Class | Port Co-Location | Boundary Direction | Description & Field Structure | Governing Invariants |
| :--- | :--- | :--- | :--- | :--- |
| **`WatcherStatusDTO`** | `core/ports/driving/telemetry_port.py` | Driving Port Return | Status query DTO returning telemetry operational snapshot (`is_active: bool`, `monitored_directory: str \| None`, `active_journal: str \| None`). | `HEXA-TRUTH-04, 28` |
| **`StartMonitoringCommand`** | `core/ports/driving/telemetry_port.py` | Driving Port Parameter | Input parameter command initiating telemetry watcher (`journal_dir: Path \| None`, `poll_interval: float \| None`). | `HEXA-TRUTH-04, 26, 28` |
| **`FileIngestionEventDTO`** | `core/ports/driven/watcher_port.py` | Driven Port Callback | Immutable data-plane envelope emitted by `StreamSourcePort` on raw byte read (`event_id: UUID`, `timestamp: datetime`, `file_kind: str`, `target_path: Path`, `raw_payload: bytes`, `start_offset: int`, `end_offset: int`, `line_number: int \| None`, `part: int \| None`, `raw_hash: str`). | `HEXA-TRUTH-04, 28` |
| **`WatcherAuditEventDTO`** | `core/ports/driven/watcher_port.py` | Driven Port Callback | Immutable control-plane operational event emitted by `StreamSourcePort` (`timestamp: datetime`, `action: str`, `target_path: Path`, `detail: str`). | `HEXA-TRUTH-04, 28` |
| **`TelemetryPayloadDTO`** | `core/ports/driven/egress_port.py` | Driven Port Parameter | Normalized outbound payload transmitted to `DiscreteSinkPort` (`topic: str`, `timestamp: datetime`, `payload_bytes: bytes`, `metadata: tuple[tuple[str, str], ...]`). | `HEXA-TRUTH-04, 24, 28` |

### 4.3 Use Case Architecture & Inventory

In strict accordance with `HEXA-TRUTH-11` (Lexical & Structural Use Case Invariants), `HEXA-TRUTH-12` (Inversion of Control), `HEXA-TRUTH-13` (Framework Agnosticism), `HEXA-TRUTH-14` (Stateless Interactor Invariants), and `HEXA-TRUTH-20` (Driving Port Exclusivity):
* Use case classes must match `^[A-Z][a-zA-Z0-9]+UseCase$` starting with an approved imperative verb (`Check`, `Get`, `Find`, `Create`, `Update`, `Delete`, `Execute`, `Process`, `Verify`, `Sync`, `Register`, `Submit`).
* Use cases must define constructor dependency injection in `__init__`, binding **only** abstract driven ports. Concrete adapter instantiation is strictly forbidden (`HEXA-TRUTH-12`).
* Use cases are stateless interactors: mutating `self.*` outside `__init__` is forbidden (`HEXA-TRUTH-14`).
* Use cases must implement exactly one driving port (`HEXA-TRUTH-20`). Adapters must never implement driving ports.
* Direct network calls, file system I/O, or OS thread management are strictly forbidden within use cases (`HEXA-TRUTH-05, 15`).

To satisfy the retained ports and adapters in `ed-telemetry`, the following use cases are established:

| Target Use Case Class | Implemented Driving Port | Injected Driven Port(s) | Verb Prefix | Business Capability & Responsibilities |
| :--- | :--- | :--- | :--- | :--- |
| **`GetWatcherStatusUseCase`** | `GetWatcherStatusPort` | `WatcherPort` | `Get` | Queries the operational state of the telemetry watcher adapter and returns an immutable `WatcherStatusDTO`. |
| **`ProcessTelemetryStreamUseCase`** | `ProcessTelemetryStreamPort` | `WatcherPort`, `EgressPort` | `Process` | Attaches handlers to `StreamSourcePort`, receives `FileIngestionEventDTO` data envelopes, normalizes them, and routes them to `EgressPort.send()`. |
| **`SyncJournalSnapshotUseCase`** | `SyncJournalSnapshotPort` | `WatcherPort`, `EgressPort` | `Sync` | Interrogates active snapshot files via the watcher subsystem, extracts latest known-state data, and emits point-in-time synchronization payloads to egress sinks. |

### 4.4 Discarded Legacy Components

The following legacy components are intentionally retired and will not be migrated into `src/ed_telemetry/`:
* `src/services/registry/` (`base.py`, `watcher.py`, `egress.py`): Replaced by static dependency injection and explicit factory wiring in `bootstrap/container.py`.
* `src/services/bootstrap.py`: Superseded by template composition root `bootstrap/container.py`.
* `src/services/context.py` (`ApplicationContext`): Removed; driving adapters interact directly with use cases injected by `bootstrap/container.py`.
* `src/services/base.py`, `src/services/watcher.py`, `src/services/exceptions.py`: Application orchestration logic is refactored into stateless use cases (`core/use_cases/`).
* `src/services/dto/` (`base.py`, `watcher.py`): Converted to frozen, immutable dataclasses co-located within `core/ports/driving/` or `core/ports/driven/` (`HEXA-TRUTH-28`).

---

## 5. Survey of Enforcement Mechanisms: Retained vs. Superseded

| Legacy Enforcement Mechanism | Scope | Disposition | Rationale |
| :--- | :--- | :--- | :--- |
| **Pre-commit: `check-added-large-files`** | Git Pre-commit | **RETAINED** | Added to downstream `.pre-commit-config.yaml` to prevent accidental commits of large telemetry test logs. |
| **Pre-commit: Formatting & Linting** | Git Pre-commit | **SUPERSEDED** | Standardized via template's `ruff` (v0.7.3+), `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`. |
| **CI: Multi-OS Matrix** | GitHub Actions | **RETAINED** | Preserves Ubuntu and Windows test runner execution matrix across Python 3.12/3.13, updated to use Astral `uv`. |
| **AST Linter: `lint_lifecycle_exclusivity.py`** | Scripts / CI | **SUPERSEDED** | Replaced by `tests/architecture/test_boundaries.py` (`HEXA-TRUTH-05`), which verifies zero lifecycle pollution across core domain and use cases. |
| **Runtime Reflection: `test_boundary_reflection.py`** | Pytest Suite | **SUPERSEDED** | Retired alongside `src/services/` and `ApplicationContext`. Replaced by `tests/architecture/test_boundaries.py` which statically audits AST. |
| **Policy Tests: `test_path_policies.py`** | Pytest Suite | **SUPERSEDED** | Enforced legacy interaction paths across deprecated service classes. Superseded by template boundary tests. |
| **Registry Tests: `test_adapter_registry.py`** | Pytest Suite | **DISCARDED** | Dynamic adapter registries are completely retired. |
| **Import Linter Contracts (`.importlinter`)** | Boundary Check | **SUPERSEDED** | Legacy contracts (`Invariant A`, `B`, `G`, `D`, `C`, `P3`) are replaced by template's Jinja-rendered hexagonal contracts. |

---

## 6. Pytest Test Suite Categorization & Migration

Of the 106 existing unit tests:
* **67 Tests Retained Directly**:
  - `test_path_discovery.py` (22 tests) -> `tests/unit/adapters/test_path_discovery.py`
  - `test_snapshot_identifier.py` (14 tests) -> `tests/unit/adapters/test_snapshot_identifier.py`
  - `test_journal_selector.py` (12 tests) -> `tests/unit/adapters/test_journal_selector.py`
  - `test_ingestion_engine.py` (8 tests) -> `tests/unit/adapters/test_ingestion_engine.py`
  - `test_watcher_adapter.py` (5 tests) -> `tests/unit/adapters/test_watcher_adapter.py`
  - `test_windows_simulant.py` (2 tests) -> `tests/unit/adapters/test_windows_simulant.py`
  - `test_domain_ports.py` (partially retained: 4 tests covering protocol hierarchy & lifecycle policies) -> `tests/unit/core/test_domain_ports.py`
* **39 Tests Discarded / Replaced**:
  - `test_domain_isolation.py` (1 test): Superseded by `test_boundaries.py`.
  - `test_boundary_reflection.py` (8 tests): Obsolete after service layer retirement.
  - `test_path_policies.py` (6 tests): Obsolete after service layer retirement.
  - `test_adapter_registry.py` (5 tests): Discarded with registry.
  - `test_watcher_service.py` (6 tests): Replaced by `test_watch_telemetry_use_case.py`.
  - `test_bootstrap.py` (3 tests): Replaced by `test_container.py`.
  - `test_application_scaffolding.py` (5 tests): Discarded with legacy scaffolding.
  - `test_domain_ports.py` (5 tests covering dynamic registry validation): Discarded.

---

## 7. Migration Sequence and Copier Strategy

The refactoring will be executed on a dedicated refactor branch (`refactor/hexagonal-template-alignment`) via the following sequence:

1. **Phase 1: Source Refactoring to Single-Root Package**
   - Create `src/ed_telemetry/` directory hierarchy.
   - Relocate domain models and exceptions to `src/ed_telemetry/core/domain/`.
   - Update port definitions under `src/ed_telemetry/core/ports/{base.py,driven/,driving/}`.
   - Refactor infrastructure modules to `src/ed_telemetry/adapters/driven/`.
   - Create stateless use cases under `src/ed_telemetry/core/use_cases/`.
   - Implement `src/ed_telemetry/bootstrap/container.py`.
   - Create test doubles in `tests/doubles/` (`FakeWatcherAdapter`, `FakeEgressAdapter`).
   - Remove deprecated directories (`src/services/`, `src/domain/`, `src/infrastructure/`, `src/interfaces/`).

2. **Phase 2: Copier Invocation & Template Scaffolding**
   - Apply `python-hexagonal-template` using Copier:
     ```bash
     copier copy --trust \
       --data project_name="ed-telemetry" \
       --data project_slug="ed-telemetry" \
       --data package_name="ed_telemetry" \
       --data python_version="3.12" \
       --data include_architecture_governance=false \
       /home/michael/src/github.com/mnaatjes/python-hexagonal-template .
     ```
   - Retain existing repository governance while merging updated `pyproject.toml`, `.importlinter`, and `tests/architecture/test_boundaries.py`.

3. **Phase 3: Test Suite & Boundary Verification**
   - Update import paths in retained tests to target `ed_telemetry.*`.
   - Run `pytest tests/architecture/test_boundaries.py` to ensure all 28 Hexagonal Truths pass.
   - Run `lint-imports` and `scripts/verify.py`.
   - Verify CI matrix builds under Astral `uv`.

---

## 8. Consequences

### Positive
* **Zero Custom Linter Debt:** Eliminates bespoke AST scripts and reflection audit modules in favor of standardized hexagonal AST tests.
* **Pure Decoupled Core:** Domain and use cases are 100% pure Python, transport-agnostic, and completely isolated from OS threads and file I/O.
* **Deterministic Offline Testing:** Full compliance with `HEXA-TRUTH-27` guarantees test doubles exist for all external boundaries.
* **Extensible Driving Layer:** Paves a clean path for subsequent additions of MCP servers, REST APIs, or enhanced TUIs without altering core logic.

### Negative / Trade-Offs
* **Breaking Import Changes:** Internal modules will no longer be accessible via top-level `domain`, `infrastructure`, or `services` imports.
* **Test Suite Churn:** 39 obsolete tests are retired, requiring net-new use case tests to achieve full coverage parity.
