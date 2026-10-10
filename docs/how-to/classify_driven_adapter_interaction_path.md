---
title: "How-To: Classify a Driven Adapter into Hexagonal Interaction Paths"
tags: ["how-to", "diataxis", "adapters", "hexagonal", "paths", "architecture"]
created_at: "2026-10-10"
last_updated_at: "2026-10-10"
---

# How-To: Classify a Driven Adapter into Hexagonal Interaction Paths

This guide provides a step-by-step practical procedure for contributors and maintainers to classify newly authored Driven Adapters (`src/infrastructure/`) into one of the **Four Canonical Hexagonal Interaction Paths** governed by [ADR 0016](../../architecture/adr/0016_interaction_path_governance_and_enforcement_policies.md) and [SDD-014](../../architecture/designs/0014_interaction_path_governance_and_enforcement_policies.md).

---

## Prerequisites

Before classifying an adapter, ensure:
1. You have defined its domain boundary port in `src/domain/ports/` inheriting from `Port`.
2. You have identified whether the adapter requires an active OS execution loop (threads, async tasks) or operates point-in-time.

---

## Step 1: Evaluate Concurrency Archetype (Active vs. Passive)

Inspect the methods and execution model of your driven adapter:

* **Does your adapter spawn or manage an operating system background thread or loop?**
  * **YES:** Your adapter **must** implement `LifecyclePort` (`start()`, `stop()`, `@property is_active`).
    - **Classification:** Route directly to **Path 1 (Lifecycle Supervisor)**.
    - **Governing Rule (Policy P1):** Only Path 1 supervisors (`DaemonService`) are permitted to invoke `.start()` or `.stop()`.
  * **NO:** Your adapter is a **Passive Adapter**. Proceed to Step 2.

---

## Step 2: Determine Data Flow Directionality

Examine how telemetry data moves across the port boundary:

* **Scenario A: Continuous Inbound Stream (`StreamSourcePort`):**
  - Your adapter produces an open-ended stream of events (e.g. `FileSystemWatcher`).
  - *If data flows into downstream transmitters:* Route to **Path 1 (`DaemonService`)**.
  - *If data flows directly to an interactive terminal UI or WebSocket observer:* Route to **Path 4 (`TelemetryStreamService`)**.

* **Scenario B: Outbound Broadcast Sink (`DiscreteSinkPort`):**
  - Your adapter receives payloads to transmit to an external endpoint (e.g. `NullTransmitter`, Discord webhook, WebSocket client).
  - *Routing:* Register your adapter inside `EgressRegistry`. It will be broadcast to by the Path 1 pipeline.
  - **Governing Rule (Policy P2):** Your sink must **never** declare `.start()` or `.stop()`.

* **Scenario C: Point-in-Time Request-Response (`PathDiscovererPort` or query ports):**
  - Your adapter performs an on-demand operation (e.g. resolving a folder, reading a single hardware metric).
  - *Routing:* Route to **Path 2 (Driven Task Facade)**. Encapsulate it in a dedicated application service (e.g. `PathDiscoveryService`).

---

## Step 3: Check for Pure In-Memory Logic (Zero-Adapter Path)

* **Does your logic perform any file access, network socket communication, or OS system calls?**
  - **NO:** If the code only validates schemas, parses data strings, or computes values, **do not create a driven adapter or port**.
  - *Routing:* Route to **Path 3 (Pure Domain Facade)**. Implement pure business entities in `src/domain/models/` and encapsulate them in a pure service (e.g. `JournalSchemaService`).
  - **Governing Rule (Policy P3):** Path 3 services are forbidden from importing `infrastructure` or `services.registry`.

---

## Step 4: Verification and Quality Gate Check

Once your adapter and managing service are classified and implemented, verify that your code adheres to all architectural boundaries:

```bash
# 1. Run the AST lifecycle exclusivity linter (Policy P1):
.venv/bin/python scripts/lint_lifecycle_exclusivity.py

# 2. Verify import-linter hexagonal boundaries (Policy P3):
.venv/bin/lint-imports

# 3. Run the interaction path test suite:
.venv/bin/pytest tests/unit/test_path_policies.py
```

All quality gates must pass before submitting your pull request.
