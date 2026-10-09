---
title: "ADR 0012: Pure Hexagonal Source Topology and Satellite SDK Segregation"
status: "accepted"
date: "2026-10-09"
tags: ["architecture", "adr", "topology", "hexagonal", "packaging", "src", "sdk", "boundaries", "invariants", "madr"]
supersedes: [
    "architecture/adr/0001_architectural_vision_and_operational_concept.md",
    "architecture/adr/0002_verification_tooling_and_versioning_lifecycle.md"
]
---

# ADR 0012: Pure Hexagonal Source Topology and Satellite SDK Segregation

## 1. Context and Problem Statement

In [ADR 0001](0001_architectural_vision_and_operational_concept.md) and [ADR 0002](0002_verification_tooling_and_versioning_lifecycle.md), the repository established a flat monorepo layout placing all Python codebases under a single root directory: `packages/` (`ed_domain`, `ed_watcher`, `ed_egress`, `ed_sdk`, `ed_app`).

Following the completion of the Application Service Layer scaffolding ([ADR 0010](0010_application_service_layer_and_boundary_contracts.md)) and the onboarding of `WatcherService` ([ADR 0011](0011_watcher_telemetry_application_service.md)), critical architectural tensions have emerged in this physical layout:

1. **Category Confusion in Geographic Proximity:**
   - `packages/ed_app/` currently houses both **Driving Surfaces** (`ed_app.cli`, future `ed_app.api`, `ed_app.mcp`) and the **Application Service Layer** (`ed_app.services`, `ed_app.context`, `ed_app.dto`, `ed_app.bootstrap`).
   - Co-locating an executable application target alongside passive domain (`ed_domain`) and infrastructure (`ed_watcher`, `ed_egress`) libraries in a single flat `packages/` folder obscures the Hexagonal hierarchy.
2. **The SDK "Odd-Man-Out" Tension:**
   - In [ADR 0001](0001_architectural_vision_and_operational_concept.md) and [ADR 0004](0004_os_path_discovery_and_filesystem_research_framework.md), `ed_sdk` was conceived as a development, research, and simulation harness.
   - However, placing `ed_sdk` inside `packages/` treats it as a production runtime package. This creates structural awkwardness: production packages are strictly forbidden from importing `ed_sdk` (Invariant B), while `ed_sdk` needs to import and exercise adapters across the codebase for test fixtures and mock streams.
3. **Domain Pollution vs. Adapter-Local Models:**
   - `ed_watcher` contains necessary internal concepts (`StreamPosition`, `JournalCandidate`, `SnapshotIdentifier`, `FileIngestionEvent`). These are **adapter-local models** specific to operating system file I/O, not universal game entities.
   - In a pure architecture, these must remain private to the infrastructure layer and must **never** be moved to the core domain, while the overall directory tree must visibly reflect the 4 Clean Architecture quadrants.

We need an architectural decision establishing the canonical physical layout of the repository: replacing the flat `packages/` directory with a **Pure Hexagonal `src/` tree** and a dedicated **Satellite `sdk/` tree**.

---

## 2. Decision Drivers

* **Topological 1-to-1 Mapping with Hexagonal Architecture:** The directory structure must physically mirror the 4 quadrants of Clean / Hexagonal Architecture without conflating layers.
* **Domain Purity Preservation:** Filesystem-specific models (`StreamPosition`, `JournalCandidate`) must remain encapsulated within the infrastructure adapter and never pollute the core domain.
* **Clean Separation of the Satellite SDK:** The SDK must be recognized as a **Satellite Development Kit & Simulation Harness**, residing strictly outside the production `src/` runtime while maintaining full power to simulate, mock, and test the production layers.
* **Deterministic Machine Enforcement:** All existing boundary invariants (A, B, C, D, G) must be mechanically mapped and preserved across `import-linter`, `mypy`, and `verify.py`.
* **Zero Ambiguity for Integrators:** Any engineer inspecting the root filesystem must immediately know:
  - Where pure domain rules live (`src/domain/`).
  - Where use cases and DTOs live (`src/services/`).
  - Where OS/hardware adapters live (`src/infrastructure/`).
  - Where user front doors live (`src/interfaces/`).
  - Where developer test/simulation harnesses live (`sdk/`).

---

## 3. Considered Options

* **Option 1: Retain Flat `packages/` Directory (Status Quo)**
  - *Pros:* Zero immediate file movements.
  - *Cons:* Ongoing cognitive friction; Driving Surfaces, Services, and Infrastructure remain geographically conflated.
* **Option 2: Coarse `apps/` and `libs/` Segregation**
  - *Pros:* Separates executable `ed_app` from libraries.
  - *Cons:* Still conflates Domain, Infrastructure, and Application Services inside `libs/`; does not solve the SDK satellite boundary.
* **Option 3: Pure Hexagonal `src/` with Satellite `sdk/` (Chosen)**
  - *Pros:* Textbook Hexagonal / Clean Architecture; physically segregates Core Domain, Application Services, Infrastructure Adapters, and Driving Surfaces; places the SDK into an explicit satellite development role outside production runtime code; eliminates all architectural ambiguity.
  - *Cons:* Requires updating Python module import paths across the codebase and realigning `import-linter` contracts.

---

## 4. Decision Outcome

Chosen Option: **Option 3: Pure Hexagonal `src/` with Satellite `sdk/`.**

We will decommission the flat `packages/` directory and establish the following root directory topology:

```
src/                         # 100% PRODUCTION RUNTIME (The Production Hexagon)
├── domain/                  # 100% PURE CORE (Hexagon Center)
│   ├── engine.py            # TelemetryEngine
│   └── ports/               # WatcherPort, EgressPort
│
├── services/                # 100% APPLICATION SERVICE LAYER (Use Cases & DTOs)
│   ├── bootstrap.py         # Composition Root (build_application_context, build_engine)
│   ├── context.py           # ApplicationContext (frozen dataclass)
│   ├── exceptions.py        # ApplicationServiceError hierarchy
│   ├── dto/                 # DataTransferObject protocols, WatcherStatusDTO
│   └── watcher.py           # WatcherService (queries WatcherPort)
│
├── infrastructure/          # 100% DRIVEN ADAPTERS (Secondary / External I/O)
│   ├── watcher/             # FileSystemWatcher, PathDiscoverer, JournalSelector, Reactor
│   └── egress/              # NullTransmitter, future HttpTransmitter
│
└── interfaces/              # 100% DRIVING SURFACES (Primary Adapters / Front Doors)
    ├── cli/                 # Terminal commands & daemon smoke runner
    ├── api/                 # Future: FastAPI REST server
    └── mcp/                 # Future: Model Context Protocol AI tools

sdk/                         # SATELLITE DEVELOPMENT KIT (Simulation & Recon Harness)
├── recon/                   # Offline log acquisition & anonymization
└── simulation/              # Synthetic journal streams, Wine simulant helpers

tests/                       # VERIFICATION SUITES
├── unit/                    # Fast isolated tests
└── integration/             # End-to-end and Wine cross-platform tests

docs/                        # DIÁTAXIS OPERATOR PLANE (Living Runbooks & References)
architecture/                # ENGINEERING PLANE (ADRs, SDDs, RFCs, Use Cases, Risk)
```

---

## 5. Architectural Boundary & Invariant Alignment Ledger

To guarantee that zero boundary guarantees are diluted or compromised during this refactor, the following master matrix defines how all established static, runtime, and adapter-local policies are mapped to the new topology:

### 5.1 Static Architectural Boundaries (Enforced by `import-linter` & `mypy`)

| Invariant / Policy | Scope & Intent | Declaration Location | Enforcement Mechanism | Current Rule (`packages/`) | New Rule (`src/` & `sdk/`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Invariant A** | **Domain Purity**<br/>(Zero external I/O or sibling imports) | ADR 0001 (Sec 6.1)<br/>ADR 0010 (Sec 3.5) | `import-linter`<br/>`pyproject.toml`<br/>`scripts/verify.py` | `source = ["ed_domain"]`<br/>`forbidden = ["ed_watcher", "ed_egress", "ed_app", "ed_sdk", "httpx", "socket", ...]` | `source = ["domain"]`<br/>`forbidden = ["infrastructure", "services", "interfaces", "sdk", "httpx", "socket", "watchdog", ...]` |
| **Invariant B** | **SDK Satellite Isolation**<br/>(Production code forbidden from SDK) | ADR 0001 (Sec 6.1)<br/>ADR 0004 (Sec 2) | `import-linter`<br/>`pyproject.toml`<br/>`scripts/verify.py` | `source = ["ed_domain", "ed_watcher", "ed_egress", "ed_app"]`<br/>`forbidden = ["ed_sdk"]` | `source = ["domain", "infrastructure", "services", "interfaces"]`<br/>`forbidden = ["sdk"]`<br/>*(Entire `src/` tree forbidden from `sdk/`)* |
| **Invariant G** | **Infrastructure Adapter Isolation**<br/>(Interfaces & services cannot import adapters) | ADR 0010 (Sec 3.5)<br/>ADR 0011 (Sec 3) | `import-linter`<br/>`pyproject.toml`<br/>`scripts/verify.py` | `source = ["ed_app.cli", "ed_app.services"]`<br/>`forbidden = ["ed_watcher", "ed_egress"]` | `source = ["interfaces", "services.watcher", "services.dto"]`<br/>`forbidden = ["infrastructure"]`<br/>*(Only `services.bootstrap` may import `infrastructure`)* |
| **Invariant D** | **Downward Dependency Layering**<br/>(Strict downward ordering within application) | ADR 0010 (Sec 3.5)<br/>ADR 0011 (Sec 5) | `import-linter`<br/>`pyproject.toml`<br/>`scripts/verify.py` | `layers = ["ed_app.cli", "bootstrap", "context", "services", "dto", "exceptions"]` | `layers = ["interfaces", "services.bootstrap", "services.context", "services.watcher", "services.dto", "services.exceptions"]` |
| **Invariant C** | **Protocol Framework Neutrality**<br/>(Services/DTOs forbidden from CLI/web libs) | ADR 0010 (Sec 3.5)<br/>SDD-008 (Sec 5.1) | `import-linter`<br/>`pyproject.toml`<br/>`scripts/verify.py` | `source = ["ed_app.services", "ed_app.dto"]`<br/>`forbidden = ["click", "fastapi", "mcp", "argparse", ...]` | `source = ["services", "services.dto"]`<br/>`forbidden = ["click", "fastapi", "starlette", "mcp", "argparse"]` |
| **Layered Flow** | **High-Level Hexagonal Layering**<br/>(Coarse inward dependency flow) | ADR 0001 (Sec 6.1)<br/>SDD-001 | `import-linter`<br/>`pyproject.toml` | `layers = ["ed_app", "ed_watcher \| ed_egress", "ed_domain"]` | `layers = ["interfaces", "services", "infrastructure", "domain"]` |
| **Static Typing** | **Strict Type Safety Across Monorepo** | ADR 0002 (Sec 3.2) | `mypy`<br/>`pyproject.toml` | `packages = ["ed_domain", "ed_watcher", "ed_egress", "ed_sdk", "ed_app"]` | `mypy_path = ["src", "sdk"]`<br/>`packages = ["domain", "services", "infrastructure", "interfaces", "sdk"]` |

---

### 5.2 Runtime & Behavioral Invariants (Enforced by Unit & Wine Test Suites)

| Invariant / Policy | Scope & Intent | Declaration Location | Enforcement Mechanism | Verification Assertion |
| :--- | :--- | :--- | :--- | :--- |
| **Invariant E** | **DTO Boundary Isolation**<br/>(Services return frozen DTOs, never mutable domain entities) | ADR 0010 (Sec 3.5)<br/>SDD-008 | `tests/unit/test_watcher_service.py`<br/>`scripts/run_wine_tests.sh` | Asserts return type satisfies `DataTransferObject` protocol and `isinstance(res, WatcherStatusDTO)` |
| **Invariant F** | **Side-Effect-Free Construction**<br/>(0 threads, 0 sockets, 0 disk I/O on bootstrap) | ADR 0003 (Sec 3.1)<br/>ADR 0010 (Sec 3.5) | `tests/unit/test_bootstrap.py`<br/>`tests/unit/test_application_scaffolding.py` | Asserts `threading.active_count()` before and after `build_application_context()` is invariant |
| **Domain Clean Isolation** | **Interpreter Module Quarantine**<br/>(Importing domain loads zero sibling packages) | ADR 0001 (Sec 6.2) | `tests/unit/test_domain_isolation.py` | Inspects `sys.modules` ensuring `import domain` loads zero `infrastructure`, `services`, or `sdk` |

---

### 5.3 Adapter-Local Encapsulation Policies (Preserved Inside `src/infrastructure/`)

| Policy | Scope & Intent | Declaration Location | Enforcement Location | Encapsulation Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Succession Invariant** | Successor journals (`02.log`, `03.log`) must always start at byte 0 (`HEAD`) | SDD-004 (Sec 3)<br/>SDD-006 (Sec 4) | `tests/unit/test_journal_selector.py`<br/>`tests/unit/test_ingestion_engine.py` | Encapsulated entirely inside `src/infrastructure/watcher/selector.py` and `tailer.py`. Never leaks to `domain/`. |
| **BLAKE2b Freshness Gate** | Identical 64-bit snapshot hashes are deduplicated without re-emission | ADR 0008 (Sec 3)<br/>SDD-006 (Sec 4) | `tests/unit/test_ingestion_engine.py`<br/>`tests/unit/test_snapshot_identifier.py` | Encapsulated inside `src/infrastructure/watcher/engine/freshness.py`. Never leaks to `domain/`. |
| **Atomic Read Envelope** | Zero-byte or non-bracketed (`{...}`) snapshot writes retry with exponential backoff | ADR 0008 (Sec 3)<br/>SDD-006 (Sec 4) | `tests/unit/test_ingestion_engine.py` | Encapsulated inside `src/infrastructure/watcher/engine/snapshot_reader.py`. Never leaks to `domain/`. |
| **Adapter-Local Models** | `StreamPosition`, `JournalCandidate`, `SnapshotCandidate` remain adapter-private | ADR 0012 (Sec 1) | AST Linter / Mypy | Declared strictly in `src/infrastructure/watcher/`. Forbidden from migrating to `src/domain/`. |


---

## 6. Supersedence of Prior Decisions

This ADR formally supersedes the physical packaging topology defined in:
1. **[ADR 0001 Section 4 & 6.1](0001_architectural_vision_and_operational_concept.md):** The physical layout placing all packages under `packages/` is superseded by the `src/` (4-quadrant Hexagon) and `sdk/` (Satellite Development Kit) structure.
2. **[ADR 0002 Section 3.1](0002_verification_tooling_and_versioning_lifecycle.md):** The packaging structure specifying `where = ["packages"]` is superseded by `where = ["src", "sdk"]`.

All semantic requirements, behavioral contracts, and quality invariants established in ADRs 0001 through 0011 remain in full legal force.

---

## 7. Consequences

### Positive
* **Architectural Purity:** The directory layout is a direct, intuitive 1:1 physical reflection of Clean / Hexagonal Architecture.
* **Elimination of Packaging Ambiguity:** Reusable domain logic, application use cases, infrastructure I/O adapters, and driving surfaces each have their own dedicated, unpolluted top-level directory.
* **True Satellite SDK:** The SDK is clearly delineated as a companion development and simulation harness residing outside the production `src/` tree, with Invariant B preventing runtime coupling.
* **Adapter Encapsulation:** File-tailing and snapshot models remain safely private inside `infrastructure/watcher/` without polluting `domain/`.

### Negative / Trade-Offs
* Requires updating module import paths across existing Python files (`from ed_watcher...` $\to$ `from infrastructure.watcher...`, `from ed_domain...` $\to$ `from domain...`, `from ed_app...` $\to$ `from services...` / `from interfaces...`).
* Requires updating path references across `pyproject.toml`, test scripts, Wine test runners, and Diátaxis documentation.

---

## 8. Elaboration Gate & Phased Execution

Upon approval of this ADR, implementation will NOT proceed immediately in this phase. The project will advance into the **Unified Process Elaboration Phase**, requiring:

1. **SDD-009 / SDD-010 Specification:** A detailed Software Design Document outlining the atomic file-movement map, automated search-and-replace AST script, and verification gates.
2. **Implementation Execution:** Execution of directory moves, import updates, and configuration adjustments on a dedicated feature branch.
3. **Verification Acceptance:** Complete passage of `scripts/verify.py` (Ruff, Mypy, Import-Linter 6 contracts, Pytest, CLI smoke test) and `scripts/run_wine_tests.sh` under Windows Python via Wine.
