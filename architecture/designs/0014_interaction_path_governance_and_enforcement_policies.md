---
title: "SDD-014: Interaction Path Governance, Topology Invariants, and Automated Enforcement Policies"
status: "proposed"
authors: ["@mnaatjes"]
reviewers: ["Systems Engineering Team"]
created_at: "2026-10-10"
last_updated_at: "2026-10-10"
related_adrs: ["architecture/adr/0016_interaction_path_governance_and_enforcement_policies.md"]
related_rfcs: []
tags: ["architecture", "sdd", "hexagonal", "interaction-paths", "policies", "enforcement", "services"]
---

# SDD-014: Interaction Path Governance, Topology Invariants, and Automated Enforcement Policies

This Software Design Document specifies the architecture, component topology, dynamic sequence models, and machine-enforced verification harness for the **Four Canonical Hexagonal Interaction Paths** and binding policies **P1 through P4** governed by [ADR 0016](../adr/0016_interaction_path_governance_and_enforcement_policies.md).

---

## 1. System Overview & Problem Context

In Pure Hexagonal Architecture ([ADR 0012](../adr/0012_segregation_of_root_monorepo_topology_into_apps_and_libs.md)), the Application Service Layer (`src/services/`) mediates all interactions between Driving Surfaces (`src/interfaces/`), Domain Entities (`src/domain/`), and Driven Adapters (`src/infrastructure/`).

### Identified Architectural Deficiencies Prior to this Design
1. **Unregulated Service Topologies:** No formal taxonomy classified whether an application service acted as a process supervisor, a task delegate, an in-memory rule engine, or a reactive push stream.
2. **Lifecycle Proliferation Risk:** Without Policy P1, individual task facades risked instantiating worker threads directly, creating competing lifecycle controllers and uncoordinated pipelines.
3. **Passive Adapter Ambiguity:** Without Policy P2, passive outbound sinks lacked explicit guarantees separating their discrete interfaces (`send()`) from active lifecycle methods (`start()`, `stop()`).
4. **Unchecked Dependency Creep in Domain Facades:** Without Policy P3, in-memory validation services risked taking convenience dependencies on infrastructure file readers or driven registries.
5. **Runtime Object Tunneling:** Without Policy P4, external callers could bypass service facades via transitive attribute traversal across `ApplicationContext` or DTO fields.

SDD-014 provides the detailed architectural blueprint to codify the four canonical paths and implement automated CI quality gates that machine-enforce Policies P1 through P4.

---

## 2. Architectural Invariants & Quality Attributes

This subsystem enforces four primary policies backed by machine-validated quality attributes:

1. **Policy P1 (Active Lifecycle Exclusivity):**
   * *Invariant:* Background threads and execution loops are restricted exclusively to adapters implementing `LifecyclePort`.
   * *Exclusivity:* Invoking `.start()` and `.stop()` is permitted **only** within Path 1 Lifecycle Supervisors (`DaemonService`).
   * *Clause P1.1:* Adapters implementing `LifecyclePort` may be encapsulated by companion Path 2 facades strictly for on-demand capabilities residing outside the continuous lifecycle loop (status queries, diagnostics).
2. **Policy P2 (Passive Sink Capability Invariant):**
   * *Invariant:* Driven adapters implementing `DiscreteSinkPort` must remain purely passive (`send()` only). They must not declare background execution loops or lifecycle management methods.
3. **Policy P3 (Pure Domain Isolation Invariant):**
   * *Invariant:* Path 3 application services represent pure computational logic. They have zero imports and zero dependencies on `src/infrastructure/` and `src/services/registry/`.
4. **Policy P4 (Gateway Placement & DTO Purity Invariant):**
   * *Invariant:* Driving adapters access application services exclusively through `ApplicationContext`.
   * *Purity:* Every public service method accepts only primitives or immutable Command DTOs, and returns only primitives or immutable Outbound Query DTOs (`@dataclass(frozen=True)`). Zero domain or infrastructure types may be leaked.

---

## 3. Structural Component & Protocol Hierarchy Model

The following diagram defines the structural topology uniting the four interaction paths:

```mermaid
classDiagram
    direction TB

    class ApplicationContext {
        <<immutable container / gateway>>
        +daemon_service: DaemonService
        +watcher_service: WatcherService
        +schema_service: JournalSchemaService
        +stream_service: TelemetryStreamService
    }

    class BaseApplicationService {
        <<protocol / interface>>
        +service_name: str
    }

    class DaemonService {
        <<Path 1: Lifecycle Supervisor>>
        -_watcher_registry: WatcherRegistry
        -_egress_registry: EgressRegistry
        -_state: DaemonState
        +start() None
        +stop() None
        +pause() None
        +resume() None
        +get_status() DaemonStatusDTO
    }

    class WatcherService {
        <<Path 2: Driven Task / Subsystem Facade>>
        -_watcher_registry: WatcherRegistry
        +get_status() WatcherStatusDTO
        +get_active_journal() Optional[str]
    }

    class JournalSchemaService {
        <<Path 3: Pure Domain Facade>>
        -_parser: JournalEventParser
        +validate_entry(raw_json: str) ValidationResultDTO
    }

    class TelemetryStreamService {
        <<Path 4: Reactive Subscription Stream>>
        -_source: StreamSourcePort
        -_observers: List[Callable]
        +subscribe(callback) None
        +unsubscribe(callback) None
    }

    class LifecyclePort {
        <<domain port / capability>>
        +start() None
        +stop() None
        +is_active: bool
    }

    class DiscreteSinkPort {
        <<domain port / capability>>
        +send(payload: Mapping) None
    }

    class StreamSourcePort {
        <<domain port / capability>>
        +register_event_handler(handler) None
    }

    class FileSystemWatcher {
        <<driven adapter (infrastructure)>>
        +start() None
        +stop() None
        +is_active: bool
        +register_event_handler(handler) None
    }

    class NullTransmitter {
        <<driven adapter (infrastructure)>>
        +send(payload: Mapping) None
    }

    %% Hierarchy & Relationships
    BaseApplicationService <|.. DaemonService : implements
    BaseApplicationService <|.. WatcherService : implements
    BaseApplicationService <|.. JournalSchemaService : implements
    BaseApplicationService <|.. TelemetryStreamService : implements

    ApplicationContext o-- DaemonService : exposes
    ApplicationContext o-- WatcherService : exposes
    ApplicationContext o-- JournalSchemaService : exposes
    ApplicationContext o-- TelemetryStreamService : exposes

    DaemonService --> LifecyclePort : supervises (Policy P1)
    DaemonService --> DiscreteSinkPort : broadcasts to (Policy P2)
    WatcherService --> StreamSourcePort : queries
    TelemetryStreamService --> StreamSourcePort : subscribes to

    LifecyclePort <|.. FileSystemWatcher : implements
    StreamSourcePort <|.. FileSystemWatcher : implements
    DiscreteSinkPort <|.. NullTransmitter : implements
```

---

## 4. Dynamic Sequence Models

### 4.1 Path 1 Sequence: Lifecycle Supervision & Selective Activation

```mermaid
sequenceDiagram
    autonumber
    participant CLI as Driving Adapter (CLI)
    participant CTX as ApplicationContext
    participant DS as DaemonService (Path 1)
    participant W_REG as WatcherRegistry
    participant E_REG as EgressRegistry
    participant W as FileSystemWatcher (LifecyclePort)
    participant TX as NullTransmitter (DiscreteSinkPort)

    CLI->>CTX: app_ctx.daemon_service.start()
    CTX->>DS: start()

    Note over DS: Policy P1: Transition STOPPED -> STARTING
    DS->>W_REG: get_active()
    W_REG-->>DS: watcher_adapter

    Note over DS: Wire continuous data pipeline
    DS->>W: register_event_handler(_handle_inbound_event)

    Note over DS: Selective Lifecycle Activation
    DS->>DS: isinstance(watcher, LifecyclePort) == True
    DS->>W: start()
    Note over W: Worker thread spawned

    Note over DS: Policy P2: Passive Sinks Skipped
    DS->>E_REG: get_all()
    E_REG-->>DS: [tx_adapter]
    Note over DS: tx has NO LifecyclePort (No start call)

    Note over DS: Transition STARTING -> RUNNING
    DS-->>CLI: return None
```

### 4.2 Path 2 vs. Path 3 Dynamic Sequence Comparison

```mermaid
sequenceDiagram
    autonumber
    participant CLI as Driving Adapter
    participant CTX as ApplicationContext
    participant P2 as PathDiscoveryService (Path 2)
    participant PORT as PathDiscovererPort (Domain Port)
    participant P3 as JournalSchemaService (Path 3)
    participant ENT as Pure Domain Entity

    rect rgb(240, 248, 255)
        Note over CLI,PORT: PATH 2: Driven Task Facade (External I/O)
        CLI->>CTX: app_ctx.path_discovery_service.discover_path()
        CTX->>P2: discover_path()
        P2->>PORT: resolve()
        PORT-->>P2: result (from OS / Registry)
        P2-->>CLI: JournalPathDTO (Outbound DTO)
    end

    rect rgb(255, 250, 240)
        Note over CLI,ENT: PATH 3: Pure Domain Facade (Zero I/O, Zero Adapters)
        CLI->>CTX: app_ctx.schema_service.validate(raw_json)
        CTX->>P3: validate(raw_json)
        Note over P3: No Ports or Adapters touched (Policy P3)
        P3->>ENT: validate_payload(raw_json)
        ENT-->>P3: validation_result
        P3-->>CLI: ValidationResultDTO (Outbound DTO)
    end
```

---

## 5. Machine-Enforced Verification Harness Strategy

Every policy declared in ADR 0016 is mapped to an automated test fixture executed within Tier 2 Quality Gates (`scripts/verify.py`):

| Test ID | Governing Policy | Verification Mechanism | Test File / Target | Failure Condition |
| :---: | :--- | :--- | :--- | :--- |
| **TEST-PATH-01** | Policy P1 (Lifecycle Exclusivity) | AST Inspection & Pytest | `tests/unit/test_path_policies.py` | Calls to `.start()` / `.stop()` found outside `services/daemon.py`. |
| **TEST-PATH-02** | Policy P1 (Thread Leak Guard) | Thread Count Tracking | `tests/unit/test_daemon_service.py` | `threading.active_count()` leaks threads after `daemon_service.stop()`. |
| **TEST-PATH-03** | Policy P2 (Passive Sink Capability) | Structural Type Check | `tests/unit/test_domain_ports.py` | Egress adapters claim `LifecyclePort` or declare `start`/`stop`. |
| **TEST-PATH-04** | Policy P3 (Pure Domain Isolation) | AST Import Boundaries | `import-linter` (CLI Contract) | Path 3 services import from `infrastructure` or `services.registry`. |
| **TEST-PATH-05** | Policy P4 (Gateway & DTO Purity) | Memory Graph Reflection | `tests/unit/test_boundary_reflection.py` | `ApplicationContext` or DTO fields expose domain/infrastructure types. |

---

## 6. Phased Implementation Roadmap

* **Milestone 1: Verification Harness Baseline (TEST-PATH-01 - TEST-PATH-05):**
  - Implement AST scan for lifecycle method exclusivity.
  - Implement `import-linter` contract for Path 3 domain isolation.
  - Assert egress adapter passivity in unit test suite.
* **Milestone 2: DaemonService Orchestration (Path 1 Implementation):**
  - Implement `src/services/daemon.py` with selective lifecycle gating.
  - Wire `WatcherRegistry` to `EgressRegistry` broadcasting.
  - Decommission legacy `TelemetryEngine`.
* **Milestone 3: Subsystem Facade Refactoring (Path 2 Alignment):**
  - Refactor `WatcherService` into query-only facade (removing `start()`/`stop()`).
* **Milestone 4: Diátaxis Operator Documentation:**
  - Author `docs/how-to/determine_use_case_facades.md`.
  - Author `docs/how-to/classify_driven_adapter_interaction_path.md`.
