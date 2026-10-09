---
title: "ADR 0011: Watcher Telemetry Application Service and Boundary Exposure"
status: "accepted"
date: "2026-10-09"
tags: ["architecture", "adr", "application", "services", "watcher", "dto", "boundaries", "madr"]
---

# ADR 0011: Watcher Telemetry Application Service and Boundary Exposure

## 1. Context and Problem Statement

Following the establishment of the Application Service Layer scaffolding in [ADR 0010](0010_application_service_layer_and_boundary_contracts.md) and [SDD-008](../designs/0008_application_service_layer_and_boundary_contracts.md), the system provides base abstractions (`BaseApplicationService`, `DataTransferObject`, `ApplicationContext`, `ApplicationServiceError`) with an empty service container (`services = ()`).

`ed-telemetry` has an existing, fully verified inbound driving adapter subsystem `ed_watcher` implementing `WatcherPort` ([ADR 0008](0008_file_ingestion_io_freshness_and_concurrency.md), [ADR 0009](0009_watcher_port_adapter_and_threaded_lifecycle.md)). However, driving surfaces (CLI, REST API, MCP) cannot access `ed_watcher` directly because **Invariant G** strictly prohibits driving surfaces and application services from importing `ed_watcher` or `ed_egress`.

We need to provide external consumers and driving surfaces with safe, uniform access to the watcher subsystem's operational state (active status, resolved journal directory, lifecycle control) without violating Hexagonal architectural boundaries.

---

## 2. Decision Drivers

* **Invariant G Preservation:** Driving surfaces (`cli`, `api`, `mcp`) and application services must never import `ed_watcher` directly.
* **Port-Based Inversion of Control:** The service must interact with the watcher exclusively through the domain abstraction `WatcherPort` exposed by `TelemetryEngine`.
* **Standard Operating Procedure Adherence:** The onboarding of the service must strictly execute and validate the 6-step SOP defined in `docs/how-to/add_application_service.md`.
* **Immutable DTO Boundary:** Watcher state must be conveyed through an immutable, frozen `WatcherStatusDTO` that satisfies `DataTransferObject` without leaking low-level internal pointers or file handles.
* **Side-Effect-Free Composition:** Instantiating `WatcherService` must not start threads, bind sockets, or query disk I/O.

---

## 3. Decision Outcome

Chosen Option: **Implement `WatcherService` in `packages/ed_app/services/watcher.py` backed by `WatcherStatusDTO` in `packages/ed_app/dto/watcher.py`, injected with `WatcherPort` via `TelemetryEngine`.**

### 3.1 Architectural Layout

```
packages/ed_app/
├── dto/
│   ├── base.py              # DataTransferObject protocol
│   └── watcher.py           # WatcherStatusDTO (frozen dataclass)
├── services/
│   ├── base.py              # BaseApplicationService protocol
│   └── watcher.py           # WatcherService (queries WatcherPort, returns WatcherStatusDTO)
├── context.py               # ApplicationContext (now exposes watcher_service: WatcherService)
└── bootstrap.py             # Composition Root (wires engine.watcher -> WatcherService -> context)
```

### 3.2 Component Contracts

1. **`WatcherStatusDTO` (`packages/ed_app/dto/watcher.py`):**
   ```python
   @dataclass(frozen=True)
   class WatcherStatusDTO:
       is_active: bool
       journal_dir: str | None

       def to_dict(self) -> dict[str, Any]:
           return {
               "is_active": self.is_active,
               "journal_dir": self.journal_dir,
           }
   ```
2. **`WatcherService` (`packages/ed_app/services/watcher.py`):**
   - Satisfies `BaseApplicationService` (`service_name = "watcher_service"`).
   - Injected with `WatcherPort` (or `TelemetryEngine` exposing `engine.watcher`).
   - Provides query method `get_status() -> WatcherStatusDTO`.
   - Exposes lifecycle management `start() -> None` and `stop() -> None` delegating to `WatcherPort`.
   - Never imports `ed_watcher` or `ed_egress` (fulfills Invariant G).
3. **`ApplicationContext` (`packages/ed_app/context.py`):**
   - Holds typed field `watcher_service: WatcherService`.
   - Tuples `watcher_service` into `services = (self.watcher_service,)`.

---

## 4. Consequences

### Positive
* **Complete Hexagonal Isolation:** Driving surfaces query `ctx.watcher_service.get_status()` without any direct link to `ed_watcher`.
* **Co-Equal Parity:** CLI, future REST endpoints, and MCP tools consume the identical `WatcherStatusDTO` representation.
* **Standard Verification:** Validates the newly documented `docs/how-to/add_application_service.md` procedure against an actual production adapter.

### Negative / Trade-Offs
* One additional indirection layer between the driving surfaces and the underlying `FileSystemWatcher`.

---

## 5. Architectural Invariants Enforced

* **Invariant C (Protocol Neutrality):** `WatcherService` and `WatcherStatusDTO` have zero dependencies on CLI or web frameworks.
* **Invariant D (Downward Dependency):** Layering remains strictly downward (`ed_app.cli` $\to$ `bootstrap` $\to$ `services` $\to$ `context` $\to$ `dto` $\to$ `exceptions`).
* **Invariant G (Infrastructure Adapter Isolation):** Verified by `import-linter`. Zero imports of `ed_watcher` in `ed_app.services`.
