---
title: "How-To: Determine and Create Companion Use-Case Facades"
tags: ["how-to", "diataxis", "facades", "services", "cqrs", "architecture"]
created_at: "2026-10-10"
last_updated_at: "2026-10-10"
---

# How-To: Determine and Create Companion Use-Case Facades

This runbook guides contributors and maintainers through **The Three Disambiguation Rules** to determine whether a Driven Adapter implementing `LifecyclePort` requires a companion **Path 2 Use-Case Facade** (`src/services/`), and how to author it without violating architectural lifecycle invariants.

Governed by [ADR 0016](../../architecture/adr/0016_interaction_path_governance_and_enforcement_policies.md) (Policy P1 Clause P1.1) and [SDD-014](../../architecture/designs/0014_interaction_path_governance_and_enforcement_policies.md).

---

## Prerequisites

* Your adapter implements `LifecyclePort` (and potentially `StreamSourcePort`) in `src/infrastructure/`.
* Its continuous background execution loop is supervised exclusively by `DaemonService` (Path 1).

---

## Step 1: Apply The Three Disambiguation Rules

Evaluate the capabilities of your adapter against the three criteria:

### Rule 1: The Actor Intent Test (Cockburn Sea-Level Goal)
* Does a driving actor (CLI user, API caller) need to execute an on-demand, discrete inquiry that completes immediately in a single session?
  - *Example:* "I want to check what file the watcher is tailing and whether it is active." $\rightarrow$ **Passes Rule 1.**
  - *Counter-example:* "I want to run the watcher in the background." $\rightarrow$ **Fails Rule 1** (this is continuous process supervision, owned by `DaemonService`).

### Rule 2: The Lifecycle Exclusion Boundary
* Does this capability exist **outside** the continuous event pumping loop?
  - Capabilities inside the loop (`start()`, `stop()`, event routing) **belong exclusively to `DaemonService`**.
  - Capabilities outside the loop (status queries, folder permission checks, polling rate adjustments) **justify a companion facade**.

### Rule 3: The Multi-Adapter Aggregation Principle
* If your operational query checks the health or status of multiple adapters (e.g. checking watcher health and network connectivity), aggregate them into a single high-level service (e.g. `SystemHealthService`) rather than leaking multiple low-level facades to the caller.

---

## Step 2: Decision Checklist

Use this 4-step checklist to decide whether to write a new facade method:

| Step | Evaluation Question | Action |
| :---: | :--- | :--- |
| **1** | Is the operation part of starting, stopping, or running the background loop? | **STOP.** Do not create a facade method. Belongs in `DaemonService`. |
| **2** | Does an external client require on-demand access to this capability? | If YES, proceed to Step 3. If NO, keep private inside the adapter. |
| **3** | Is it a read-only query (status, active filename, line count)? | **CREATE a Query Method** returning an immutable Outbound DTO. |
| **4** | Is it a point-in-time command (rescan directory, change log level)? | **CREATE an Action Method** accepting primitives or Inbound Command DTO. |

---

## Step 3: Implement the Companion Facade

When authoring your companion facade in `src/services/`:

1. **Inherit from `BaseApplicationService`:**
   ```python
   from domain.ports.watcher import WatcherPort
   from services.base import BaseApplicationService
   from services.dto.watcher import WatcherStatusDTO


   class WatcherService(BaseApplicationService):
       """Companion Path 2 facade for inspecting the watcher subsystem."""

       def __init__(self, watcher: WatcherPort) -> None:
           self._watcher = watcher

       @property
       def service_name(self) -> str:
           return "watcher_service"
   ```

2. **Expose strictly non-lifecycle query methods:**
   ```python
       def get_status(self) -> WatcherStatusDTO:
           """Return immutable status DTO without exposing internal thread handles."""
           return WatcherStatusDTO(
               is_active=self._watcher.is_active,
               journal_dir=str(getattr(self._watcher, "journal_dir", None)),
           )
   ```

3. **NEVER implement `start()` or `stop()`:**
   Declaring lifecycle hooks on companion facades violates **Policy P1** and will be flagged as a build-breaking violation by `scripts/lint_lifecycle_exclusivity.py`.

---

## Step 4: Verification and Quality Gate Check

Run all Tier 2 quality gates to verify compliance:

```bash
.venv/bin/python scripts/verify.py
```
