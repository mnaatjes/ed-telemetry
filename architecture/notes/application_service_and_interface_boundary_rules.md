---
title: "Application Service Layer and Interface Boundary Governance Rules"
tags: ["architecture", "notes", "governance", "boundaries", "services", "interfaces", "rules"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# Application Service Layer and Interface Boundary Governance Rules

Working ledger of governing principles and operational boundaries mediating between Driving Surfaces (`src/interfaces/`) and the Application Service Layer (`src/services/`).

---

## Core Rules

1. **Rule 1 (Sole Consumer):**
   Drivers (Driving Interfaces in `src/interfaces/`) are the **ONLY** consumers of the `ApplicationContext`. Services, domain models, and infrastructure adapters must never import, receive, or inspect `ApplicationContext`.

2. **Rule 2 (Physical Locality):**
   The Application Service Layer resides strictly within `src/services/`. All use case orchestration, application error hierarchies, and boundary data contracts belong exclusively here.

3. **Rule 3 (Composition & Access Gateway):**
   Services are instantiated by the Composition Root (`bootstrap.py`) and loaded into the `ApplicationContext` for use by Drivers. Drivers never instantiate services or secondary adapters directly.

---

## Domain Layer Structural Taxonomy (`src/domain/`)

The Domain is the pure computational center of the Hexagon (governed by Invariant A). It is strictly isolated from external I/O, framework dependencies, and operational lifecycle concerns. It is partitioned into four canonical categories:

```text
src/domain/
├── values/      # 1. Value Objects & Enums (Immutable Data Shapes)
├── entities/    # 2. Domain Entities & Aggregates (Identity + State + Invariants)
├── logic/       # 3. Domain Services & Business Rules (Pure Computations)
└── ports/       # 4. Domain Ports (Abstract Boundary Contracts)
```

### Category 1: Value Objects & Enums (Immutable Concepts)
* **Definition:** Data shapes and primitives without unique lifecycle identity. Defined solely by their attributes and equality of values. Always immutable (`frozen=True`).
* **Role:** Represent domain concepts and event schemas (e.g., `StarSystem`, `CommodityPrice`, `GameMode`, `JournalEventSchema`).
* **Invariants:** Zero external I/O, zero network or filesystem dependencies.

### Category 2: Domain Entities & Aggregates (Identity + State Invariants)
* **Definition:** Core business models possessing an explicit identity tracked across state transitions over time.
* **Role:** Enforce internal business rules and maintain consistency invariants during event ingestion (e.g., `CommanderState` tracking ship hull, cargo capacity, and fuel status; `MarketCatalog` aggregating station commodities).
* **Invariants:** Mutated exclusively through domain methods that validate state integrity; never directly modified by external adapters.

### Category 3: Domain Services & Pure Business Rules (Computations)
* **Definition:** Business algorithms and transformation logic that operate across multiple entities or value objects and do not naturally belong to a single entity.
* **Role:** Pure computations and data sanitization (e.g., jump range fuel burn calculation, PII/FID privacy filtering, telemetry payload validation).
* **Invariants:** 100% pure computational logic. Must never perform thread coordination, socket I/O, or filesystem operations.

### Category 4: Domain Ports (`src/domain/ports/`)
* **Definition:** Pure Python abstract interfaces (`typing.Protocol` or `abc.ABC`) defining the inward and outward boundary contracts required by the domain core.
* **Role:** Define how the application receives data from the world (`WatcherPort`) and emits data to external sinks (`EgressPort`).
* **Invariants:** Contain zero concrete implementation code or adapter imports.

---

### Non-Domain Separation Policy (Operational Exclusion)
* **Thread & Process Lifecycle:** Starting background daemon threads, handling OS signals (`SIGINT`, `SIGTERM`), and managing event loop workers are **operational concerns** belonging to the **Application Service Layer (`src/services/`)** or **Driven Adapters (`src/infrastructure/`)**, never the Domain Core.
* **Use-Case Orchestration:** Flow coordination across ports and adapters belongs strictly in `src/services/`.
* **Presentation & Protocol Translation:** CLI flag parsing, JSON/table formatting, and HTTP/MCP protocol framing belong strictly in `src/interfaces/`.
