---
title: "ADR 0016: Interaction Path Governance, Topology Invariants, and Automated Enforcement Policies"
status: "proposed"
date: "2026-10-10"
tags: ["architecture", "adr", "hexagonal", "interaction-paths", "policies", "invariants", "enforcement", "governance"]
---

# ADR 0016: Interaction Path Governance, Topology Invariants, and Automated Enforcement Policies

## 1. Context and Problem Statement

In Pure Hexagonal Architecture ([ADR 0012](0012_segregation_of_root_monorepo_topology_into_apps_and_libs.md)), external driving entrypoints (`src/interfaces/`) interact exclusively with the Application Service Layer (`src/services/`), which coordinates domain entities (`src/domain/`) and driven adapters (`src/infrastructure/`) through abstract domain ports (`src/domain/ports/`).

While [ADR 0014](0014_driven_adapter_registry_architecture_and_composition_root.md) established driven adapter registries and [ADR 0015](0015_domain_port_protocol_genealogy_and_lifecycle_governance.md) established the domain port capability protocol taxonomy (`LifecyclePort`, `StreamSourcePort`, `DiscreteSinkPort`), the system lacked formal architectural governance defining:
1. **The Permitted Interaction Paths:** How driving interfaces, application services, domain entities, and driven adapters combine into cohesive execution models.
2. **Path Selection Invariants:** Clear, deterministic rules specifying which interaction path a given adapter or service must employ.
3. **Automated Machine Enforcement:** Verifiable quality gates ensuring that application services do not drift into architectural anti-patterns (such as rogue thread spawning, unshielded I/O execution, or domain entity leaks).

Without explicit policies, services risk conflating responsibilities—such as attempting to start background worker threads directly within request-response query services, or leaking domain models across boundary interfaces.

We must formalize the four canonical interaction paths and declare four binding, machine-enforced governance policies (P1 through P4).

---

## 2. Decision Drivers

* **Deterministic Path Selection:** Eliminate guesswork when designing application services by anchoring path selection strictly to domain port capability archetypes and execution cadence.
* **Master Lifecycle Supervision:** Restrict concurrent OS thread management strictly to designated lifecycle supervisors, preventing rogue background thread creation in request-response facades.
* **Passive Adapter Purity:** Prevent passive outbound sinks from declaring unnecessary or confusing lifecycle hooks.
* **Pure Domain Isolation:** Ensure that purely computational domain services remain decoupled from infrastructure adapters and registries.
* **Zero-Tolerance Boundary Integrity:** Guarantee that driving surfaces interact strictly through `ApplicationContext` and receive only immutable Data Transfer Objects (DTOs) or primitives.
* **Automated Machine Enforcement:** Every policy must be backed by an executable quality gate (AST linting, static typing, or runtime reflection audits).

---

## 3. Decision Outcome

Chosen Option: **Formally Adopt the Four Canonical Hexagonal Interaction Paths and Enforce Four Binding Governance Policies (P1, P2, P3, P4) across the Application Service Layer**.

---

## 4. The Four Canonical Interaction Paths

All interactions across `ed-telemetry` must conform strictly to one of the following four canonical paths:

```text
                               +----------------------------------------+
                               | Driving Surface (CLI, Web, GUI, TUI)   |
                               +---+------------------+--------------+--+
                                   |                  |              |
                Path 1: Lifecycle  |  Path 2: Command |      Path 3: | In-memory
                & Streaming Stream |  / Driven Query  |   Validation | Computation
                                   v                  v              v
+-------------------------------------------------------------------------------+
|                       Application Service Layer (src/services/)               |
|                                                                               |
|  [Path 1] Lifecycle Supervisor (e.g. DaemonService)                           |
|           • Supervises LifecyclePort adapters (start/stop/is_active)          |
|           • Wires StreamSourcePort sources to DiscreteSinkPort sinks          |
|                                                                               |
|  [Path 2] Driven Task Facade (e.g. PathDiscoveryService)                      |
|           • Request-response delegation to Driven Port (e.g. PathDiscoverer)  |
|           • Maps domain output to Outbound Query DTO                          |
|                                                                               |
|  [Path 3] Pure Domain Facade (e.g. JournalSchemaService)                      |
|           • Zero I/O, Zero Driven Adapters, Zero Registries                   |
|           • In-memory rule validation and computation on domain models        |
|                                                                               |
|  [Path 4] Reactive Subscription Stream (e.g. TelemetryStreamService)          |
|           • Inbound stream source pushes DTOs to driving UI callbacks         |
+-------------------+-----------------------------------+-----------------------+
                    |                                   |
                    v Calls driven adapters             v Calls pure entities
+------------------------------------+ +----------------------------------------+
| Driven Adapters (src/infrastructure) | Domain Entities (src/domain/models)    |
| (FileSystemWatcher, NullTransmitter)| (JournalCandidate, FlightLog, Specs)   |
+------------------------------------+ +----------------------------------------+
```

1. **Path 1: Lifecycle Supervisor (Macro Process Control):**
   * *Role:* Continuous process supervision, thread coordination, and event stream routing.
   * *Target Adapters:* Adapters implementing `LifecyclePort` + `StreamSourcePort` (sources) and `DiscreteSinkPort` (sinks).
2. **Path 2: Driven Task Facade (Request-Response I/O):**
   * *Role:* Point-in-time external tasks, queries, or commands requiring external I/O.
   * *Target Adapters:* Driven adapters implementing specific domain query/command ports.
3. **Path 3: Pure Domain Facade (In-Memory Computation):**
   * *Role:* Computational, algorithmic, or schema validation operations requiring zero I/O.
   * *Target Adapters:* **Zero Adapters.** Interacts strictly with pure domain entities.
4. **Path 4: Reactive Subscription Stream (Observer Push):**
   * *Role:* Real-time push streaming to driving UI, TUI, or WebSocket observers.
   * *Target Adapters:* Adapters implementing `StreamSourcePort`.

---

## 5. Formal Policies, Invariants, and Machine Enforcement Contracts

The interaction paths are governed by four mandatory policies, each enforced by an explicit quality gate:

### Policy P1: Active Lifecycle Exclusivity Invariant

* **Statement:**
  Only driven adapters conforming to `LifecyclePort` (`start()`, `stop()`, `@property is_active`) may encapsulate background execution loops or OS worker threads. Furthermore, lifecycle invocation (`.start()`, `.stop()`) is **strictly exclusive** to Path 1 Lifecycle Supervisors (`DaemonService`). No Path 2 functional facade, Path 3 domain facade, or Driving Adapter may directly instantiate threads or invoke lifecycle hooks.
* **Clause P1.1 (Scope of Companion Path 2 Facades):**
  Driven adapters conforming to `LifecyclePort` may still be encapsulated by companion Path 2 functional facades (e.g. `WatcherService`) strictly for on-demand capabilities that reside outside the continuous lifecycle loop (such as read-only status introspection, pre-flight diagnostics, or declarative configuration). Such companion facades must never expose or invoke execution lifecycle methods.
* **Architectural Rationale:**
  Permitting arbitrary services or driving controllers to trigger background workers creates competing thread owners, dangling pipelines, and non-deterministic process shutdown leaks.
* **Machine Enforcement:**
  1. **Static AST Analysis:** CI gate asserting zero calls to `.start()` or `.stop()` across `src/services/` (with `services/daemon.py` as the sole whitelisted supervisor).
  2. **Type System Enforcement:** `mypy --strict` guarantees that Path 2 and Path 4 facades accept only domain ports that do not inherit from `LifecyclePort`.
  3. **Thread Leak Assertion:** Unit tests in `tests/unit/test_daemon_service.py` assert `threading.active_count()` equality before startup and after shutdown.

---

### Policy P2: Passive Sink Capability Invariant

* **Statement:**
  Driven adapters implementing `DiscreteSinkPort` (e.g. telemetry transmitters, webhook sinks) are point-in-time outbound receivers (`send()` only). They must not declare background execution loops or lifecycle management methods (`start()`, `stop()`). Outbound sinks are stateless or externally managed, and may be consumed directly by individual application services or orchestrated via collection registries.
* **Architectural Rationale:**
  Upholds the Interface Segregation Principle (ISP) established in ADR 0015. Outbound sinks do not own background execution threads and must not force artificial lifecycle management upon consumers.
* **Machine Enforcement:**
  1. **Structural Capability Verification:** `tests/unit/test_domain_ports.py` (`test_egress_adapters_are_passive`) validates that concrete driven egress adapters satisfy `DiscreteSinkPort` while remaining untainted by `LifecyclePort` (`assert isinstance(tx, DiscreteSinkPort)` and `assert not isinstance(tx, LifecyclePort)`).
  2. **Compile-Time Static Typing:** `mypy --strict` guarantees that consumers holding references typed as `EgressPort` or `DiscreteSinkPort` cannot invoke `.start()` or `.stop()`.

---

### Policy P3: Pure Domain Isolation Invariant (Zero-Adapter Path)

* **Statement:**
  Path 3 application services represent pure business computations, schema evaluations, or algorithmic transformations. They must have **zero imports and zero runtime dependencies** on `src/infrastructure/` and `src/services/registry/`. They interact exclusively with pure domain entities in `src/domain/`.
* **Architectural Rationale:**
  Prevents unnecessary technological coupling, ensures computational workflows are 100% deterministic and unit-testable without mocks, and preserves Domain Isolation (Invariant A).
* **Machine Enforcement:**
  1. **Import Linter Contract:** Statically verified on every commit via `import-linter`:
     ```ini
     [importlinter:contract:path3_pure_domain_isolation]
     name = "Invariant P3: Path 3 Services must not depend on Infrastructure or Registries"
     type = "forbidden"
     source_modules = services.schema
     forbidden_modules =
         infrastructure
         services.registry
     ```
  2. **Runtime Reflection Audit:** `audit_service_constructor_shielding` in `tests/helpers/boundary_reflection.py` asserts that all constructor arguments of Path 3 services belong strictly to `domain.models.*` or standard primitives.

---

### Policy P4: Gateway Placement and DTO Purity Invariant

* **Statement:**
  Driving adapters access application services across all four paths **strictly via `ApplicationContext`**. Every public method across all four interaction paths must accept only primitives or immutable Inbound Command DTOs, and must return strictly primitives or immutable Outbound Query DTOs (`@dataclass(frozen=True)`). No method may ever leak a domain entity, domain port protocol, adapter registry, or driven adapter instance to driving surfaces.
* **Architectural Rationale:**
  Completely eliminates Transitive Runtime Object Tunneling (Junction 1 and Junction 2) as benchmarked in ADR 0013 and SDD-011. Driving adapters (CLI, GUI, REST) cannot traverse object graphs into private domain or infrastructure classes.
* **Machine Enforcement:**
  1. **Runtime Reflection Gateway Audit (`audit_context_gateway`):** Verifies that 100% of attributes exposed on `ApplicationContext` implement `BaseApplicationService`. Flags any `domain.*` or `infrastructure.*` leakage as CRITICAL.
  2. **Runtime Reflection DTO Audit (`audit_dto_purity`):** Inspects all fields on returned DTO instances, asserting that zero field values or nested types originate from `domain.*` or `infrastructure.*`.
  3. **Compile-Time Type Analysis:** Strict typing enforced by `mypy --strict` on all service method signatures.

---

## 6. Summary of Enforcement Matrix

| Policy | Target Architectural Boundary | Verification Tool | Quality Gate Stage | Failure Action |
| :--- | :--- | :--- | :--- | :--- |
| **Policy P1** (Lifecycle Exclusivity) | `src/services/` lifecycle calls | AST Linter / Pytest | Tier 2 (`scripts/verify.py`) | Halts build; flags rogue thread lifecycle invocation. |
| **Policy P2** (Passive Sink Purity) | `src/domain/ports/egress.py` | Pytest MRO check | Tier 2 (`scripts/verify.py`) | Halts build; flags lifecycle pollution on discrete sinks. |
| **Policy P3** (Pure Domain Isolation) | Path 3 services (`services.schema`) | `import-linter` | Tier 2 (`scripts/verify.py`) | Halts build; flags illegal infrastructure/registry imports. |
| **Policy P4** (Gateway & DTO Purity) | `ApplicationContext` & DTO return types | Reflection Harness | Tier 2 (`scripts/verify.py`) | Halts build; flags Object Tunneling across Junctions 1 & 2. |

---

## 7. Consequences

### Positive
* **Architectural Predictability:** Establishes unambiguous rules for how new services and adapters must be structured and integrated.
* **Zero Runtime Tunneling:** Guarantees that driving interfaces cannot bypass service facades to manipulate internal domain or infrastructure states.
* **Clean Process Teardown:** Precludes orphaned background threads by restricting thread management to supervised Path 1 lifecycle controllers.
* **Automated Guardrails:** CI pipelines automatically catch architectural regressions without relying solely on manual code reviews.

### Negative
* Requires writing explicit Outbound DTO mappers for all service query methods, increasing initial boilerplate.
* Pure domain services must be strictly partitioned from I/O services, preventing quick "convenience" disk reads inside schema evaluators.

---

## 8. Documentation and Contributor Enablement Plan

To enable contributors and maintainers to apply these policies and disambiguation rules consistently, the following Diátaxis runbooks will be authored:

1. **`docs/how-to/determine_use_case_facades.md` (Diátaxis How-To):**
   - Practical decision checklist for determining whether an adapter requires a companion Path 2 use-case facade based on The Three Disambiguation Rules.
   - Guidelines on structuring query DTOs and shielding lifecycle execution.
   - Concrete example walkthrough contrasting `FileSystemWatcher` (Path 1) with `WatcherService` (Path 2).

2. **`docs/how-to/classify_driven_adapter_interaction_path.md` (Diátaxis How-To):**
   - Step-by-step procedure for classifying newly authored driven adapters into Paths 1 through 4 based on port capability protocols and execution cadence.
