---
title: "ADR 0012: Segregation of Root Monorepo Topology into apps/ and libs/"
status: "proposed"
date: "2026-10-09"
tags: ["architecture", "adr", "topology", "monorepo", "packaging", "apps", "libs", "madr"]
supersedes: [
    "architecture/adr/0001_architectural_vision_and_operational_concept.md",
    "architecture/adr/0002_verification_tooling_and_versioning_lifecycle.md"
]
---

# ADR 0012: Segregation of Root Monorepo Topology into apps/ and libs/

## 1. Context and Problem Statement

In [ADR 0001](0001_architectural_vision_and_operational_concept.md) and [ADR 0002](0002_verification_tooling_and_versioning_lifecycle.md), the repository established a flat monorepo layout placing all Python codebases under a single root directory: `packages/` (`ed_domain`, `ed_watcher`, `ed_egress`, `ed_sdk`, `ed_app`).

Following the completion of the Application Service Layer scaffolding ([ADR 0010](0010_application_service_layer_and_boundary_contracts.md)) and the onboarding of `WatcherService` ([ADR 0011](0011_watcher_telemetry_application_service.md)), a fundamental architectural asymmetry has emerged:

1. **Category Confusion in Geographic Proximity:**
   - `ed_domain`, `ed_watcher`, `ed_egress`, and `ed_sdk` are **passive, reusable libraries**. They contain domain rules, hardware/OS adapters, and client stubs. None of them define execution entry points (`__main__.py`).
   - `ed_app` is an **active, executable application target**. It contains the Composition Root (`bootstrap.py`), the Application Service Layer, and multiple Driving Surfaces (CLI entry point, future REST API, future MCP server).
2. **Cognitive Friction for Operators and Integrators:**
   Co-locating an executable application target alongside passive domain and infrastructure libraries in a flat `packages/` folder obscures the system hierarchy. It creates the false impression that `ed_app` is simply another peer library rather than the top-level deployable runtime that imports and orchestrates the libraries.
3. **Packaging Ambiguity:**
   External tooling and developers cannot distinguish by directory inspection which folders are distributable reusable libraries versus deployable application binaries.

We need an architectural decision establishing whether to maintain the flat `packages/` layout or segregate the repository topology into distinct `apps/` and `libs/` roots.

---

## 2. Decision Drivers

* **Topological Self-Documentation:** The directory tree should immediately communicate the difference between deployable application binaries and passive libraries without reading implementation code.
* **Preservation of Architectural Invariants:** The refactoring must preserve 100% of the boundary rules established in Invariants A, B, C, D, and G.
* **Zero Breaking Changes to Python Import Statements:** Python module names (`ed_domain`, `ed_watcher`, `ed_app`) must remain identical across all source and test files.
* **Minimal Operational Friction:** Path adjustments must be confined to build and discovery configurations (`pyproject.toml`, test scripts, verification runners).

---

## 3. Considered Options

* **Option 1: Retain Flat `packages/` Directory (Status Quo)**
  - *Pros:* Zero immediate changes to configuration or paths.
  - *Cons:* Ongoing cognitive friction; executable application target remains conflated with reusable libraries.
* **Option 2: Physical Segregation into `apps/` and `libs/` Roots (Recommended)**
  - *Pros:* Aligns with enterprise monorepo standards (Bazel, Cargo, Nx); separates runnable targets (`apps/ed_app`) from passive reusable libraries (`libs/ed_*`); immediately intuitive mental model.
  - *Cons:* Requires updating path configurations in `pyproject.toml`, `scripts/verify.py`, `scripts/run_wine_tests.sh`, and documentation links.

---

## 4. Decision Outcome

Chosen Option: **Option 2: Physical Segregation into `apps/` and `libs/` Roots.**

We will decommission the flat `packages/` root directory and establish two distinct top-level directories:

```
apps/
└── ed_app/          # Executable Application Target (Composition Root, Services, CLI, API, MCP)

libs/
├── ed_domain/       # Pure Domain Core Library (Entities, State Engine, Ports)
├── ed_watcher/      # Inbound Infrastructure Adapter Library (OS Discovery, Journal Ingestion)
├── ed_egress/       # Outbound Infrastructure Adapter Library (Transmitters, Sinks)
└── ed_sdk/          # Client SDK & Simulation Harness Library
```

### 4.1 Supersedence of Prior Decisions

This ADR formally supersedes the following structural sections of prior ADRs:
1. **[ADR 0001 Section 4 & 6.1](0001_architectural_vision_and_operational_concept.md):** The physical layout table placing all modules under `packages/` is superseded by the `apps/` and `libs/` division.
2. **[ADR 0002 Section 3.1](0002_verification_tooling_and_versioning_lifecycle.md):** The packaging structure specifying `where = ["packages"]` and verification targets is superseded.

All logical invariants (Invariant A, Invariant B, Invariant C, Invariant D, Invariant G) defined in ADR 0001, ADR 0010, and ADR 0011 remain in full legal force.

---

## 5. Consequences

### Positive
* **Immediate Structural Clarity:** Clear distinction between what executes (`apps/`) and what is imported (`libs/`).
* **Clean Packaging Boundaries:** Packaging wheels or container builds can target `apps/*` or `libs/*` independently.
* **Preserved Code Invariants:** Zero changes to internal Python `import` statements; zero changes to `import-linter` module rules.

### Negative / Trade-Offs
* Requires path updates across `pyproject.toml` (`packages.find`, `pythonpath`, `bumpversion`).
* Requires updating target arguments in `scripts/verify.py` and path insertions in `scripts/run_wine_tests.sh`.
* Requires updating directory references in `docs/` and future SDDs.

---

## 6. Migration and Verification Gates

Upon approval of this ADR, the transition will be executed under a dedicated Software Design Document (SDD) during the Elaboration phase, requiring:
1. Full pass of `scripts/verify.py` (Ruff linting, Ruff formatting, Mypy static typing, Import-Linter 6 contracts, 78 Pytest tests, CLI smoke test).
2. Clean execution of `scripts/run_wine_tests.sh` under Windows Python 3.11 via Wine.
3. Updated Diátaxis runbooks and reference documentation in `docs/`.
