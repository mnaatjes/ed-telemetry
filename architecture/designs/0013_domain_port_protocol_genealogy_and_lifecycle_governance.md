---
title: "SDD-013: Domain Port Protocol Genealogy, Capability Taxonomy, and Lifecycle Governance"
status: "proposed"
date: "2026-10-10"
tags: ["architecture", "sdd", "ports", "domain", "protocols", "lifecycle", "governance"]
---

# SDD-013: Domain Port Protocol Genealogy, Capability Taxonomy, and Lifecycle Governance

This Software Design Document specifies the architecture, protocol class hierarchy, capability taxonomy, behavioral invariants, and verification strategy for the **Domain Port Protocol Genealogy** governed by [ADR 0015](../adr/0015_domain_port_protocol_genealogy_and_lifecycle_governance.md).

---

## 1. System Overview & Problem Context

In Pure Hexagonal Architecture ([ADR 0012](../adr/0012_segregation_of_root_monorepo_topology_into_apps_and_libs.md)), all external technological systems are abstracted behind abstract **Ports** defined exclusively in the Domain Core (`src/domain/ports/`).

### Identified Deficiencies
Prior to this design:
1. **Lack of a Common Root:** `WatcherPort` (`src/domain/ports/watcher.py`) and `EgressPort` (`src/domain/ports/egress.py`) existed as independent `@runtime_checkable` protocols without a common ancestor or polymorphic marker. Generic containers like `BaseAdapterRegistry[T]` had to rely on unbounded `TypeVar("T")`.
2. **Unregulated Lifecycle Boundaries:** `WatcherPort` declared `start()`, `stop()`, and `is_active` ad-hoc, while `EgressPort` declared only `send()`. There was no formal capability protocol distinguishing active, long-running adapters from passive, discrete sinks.
3. **Impediment to Orchestration:** Without a standard `LifecyclePort` capability protocol, future Application Services (`DaemonService`) could not polymorphically manage active background adapters without hardcoding bespoke port hooks.

SDD-013 designs a clean, composable protocol genealogy based on Python `typing.Protocol` structural subtyping, establishes the canonical 5-archetype capability taxonomy, defines machine-enforced lifecycle behavioral policies, and refactors existing ports and registries.

---

## 2. Architectural Invariants & Quality Attributes

1. **Invariant 1: Domain Isolation (Pure Standard Library):**
   All protocol definitions in `src/domain/ports/` depend strictly on standard library typing constructs (`Protocol`, `runtime_checkable`, `collections.abc`). Zero imports of external frameworks or infrastructure modules.
2. **Invariant 2: Interface Segregation Principle (ISP):**
   Capabilities are factored into granular protocols (`LifecyclePort`). Passive ports (e.g. `EgressPort`) must never declare dummy lifecycle methods (`start`/`stop`).
3. **Invariant 3: Polymorphic Generic Bounds:**
   The generic base registry `BaseAdapterRegistry[T]` must bind its type parameter to `T = TypeVar("T", bound=Port)`.
4. **Invariant 4: Runtime Checkability:**
   Every protocol in the hierarchy must be decorated with `@runtime_checkable` to enable memory reflection inspection and dynamic type checks.
5. **Invariant 5: Deterministic Lifecycle Invariants (Policies L1, L2, L3):**
   Every adapter implementing `LifecyclePort` must guarantee strict idempotency (L1), bounded deterministic thread joins (L2), and shutdown exception shielding (L3).

---

## 3. Structural Component & Protocol Hierarchy Model

```mermaid
classDiagram
    direction TB

    class Port {
        <<protocol / marker>>
        """Root domain port marker protocol"""
    }

    class LifecyclePort {
        <<protocol / capability>>
        +start() None
        +stop() None
        +is_active: bool
    }

    class EgressPort {
        <<domain port / discrete sink>>
        +send(payload: Mapping[str, Any]) None
    }

    class WatcherPort {
        <<domain port / active stream source>>
        +register_event_handler(handler) None
        +register_audit_handler(handler) None
    }

    class FileSystemWatcher {
        <<driven adapter (infrastructure)>>
        -_worker_thread: Thread
        -_stop_event: Event
        +start() None
        +stop() None
        +is_active: bool
        +register_event_handler(handler) None
        +register_audit_handler(handler) None
    }

    class NullTransmitter {
        <<driven adapter (infrastructure)>>
        +send(payload: Mapping[str, Any]) None
    }

    Port <|-- LifecyclePort : specializes
    Port <|-- EgressPort : specializes (passive, zero lifecycle)
    LifecyclePort <|-- WatcherPort : specializes (active worker)
    Port <|-- WatcherPort : satisfies Port via LifecyclePort

    WatcherPort <|.. FileSystemWatcher : implements
    LifecyclePort <|.. FileSystemWatcher : implements
    Port <|.. FileSystemWatcher : implements

    EgressPort <|.. NullTransmitter : implements
    Port <|.. NullTransmitter : implements
```

---

## 4. Dynamic Sequence: Lifecycle Orchestration & Behavioral Policies

```mermaid
sequenceDiagram
    autonumber
    participant Orch as Orchestrator / DaemonService (services)
    participant Reg as WatcherRegistry (services.registry)
    participant Port as WatcherPort (domain.ports)
    participant Adp as FileSystemWatcher (infrastructure.watcher)

    Note over Orch: Verify Active Adapter Capability
    Orch->>Reg: get_active()
    Reg-->>Orch: adapter instance
    Orch->>Orch: isinstance(adapter, LifecyclePort)?

    alt Adapter implements LifecyclePort
        Note over Orch: Execute Policy L1 (Idempotent Start)
        Orch->>Adp: start()
        Adp->>Adp: Verify not already active; spawn worker thread
        Adp-->>Orch: return

        Note over Orch: Operational Phase (Streaming Events)
        Adp->>Orch: Dispatch Ingestion Events

        Note over Orch: Execute Policy L2 & L3 (Deterministic & Shielded Stop)
        Orch->>Adp: stop()
        Adp->>Adp: Set stop_event
        Adp->>Adp: Join worker thread with timeout (5.0s)
        Adp->>Adp: Suppress internal teardown errors (Policy L3)
        Adp-->>Orch: return
    else Passive Port (No Lifecycle)
        Note over Orch: Passively invoke operational methods directly
    end
```

---

## 5. Subsystem Design & Component Specifications

### 5.1 Package Locality
The port definitions reside within `src/domain/ports/`:

```text
src/domain/ports/
├── __init__.py           # Exports: Port, LifecyclePort, WatcherPort, EgressPort
├── base.py               # Root Port marker and LifecyclePort capability protocols
├── egress.py             # EgressPort (Discrete Sink Archetype)
└── watcher.py            # WatcherPort (Active Worker & Stream Source Archetypes)
```

### 5.2 Root Marker & Capability Protocols (`src/domain/ports/base.py`)

```python
"""Root domain boundary port protocols and reusable capabilities.

Governed by ADR 0015 and SDD-013.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Port(Protocol):
    """Root marker protocol for all domain boundary ports.

    Serves as the common polymorphic root for structural typing,
    generic container bounds, and reflection audits.
    """


@runtime_checkable
class LifecyclePort(Port, Protocol):
    """Capability protocol for domain ports requiring background execution management."""

    def start(self) -> None:
        """Start background workers or streaming channels asynchronously."""
        ...

    def stop(self) -> None:
        """Gracefully stop and join background workers deterministically."""
        ...

    @property
    def is_active(self) -> bool:
        """Return True if background workers are actively executing."""
        ...
```

### 5.3 Refactored `WatcherPort` (`src/domain/ports/watcher.py`)

```python
"""Abstract ports for inbound telemetry watchers."""

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from domain.ports.base import LifecyclePort

IngestionEventHandler = Callable[[Any], None]
AuditEventHandler = Callable[[Any], None]


@runtime_checkable
class WatcherPort(LifecyclePort, Protocol):
    """Contract for inbound file and telemetry watchers."""

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        """Register a callback for raw file ingestion events."""
        ...

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        """Register a callback for watcher operational audit events."""
        ...

    # NOTE: start(), stop(), and is_active are inherited from LifecyclePort.
```

### 5.4 Refactored `EgressPort` (`src/domain/ports/egress.py`)

```python
"""Abstract ports for outbound telemetry egress."""

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from domain.ports.base import Port


@runtime_checkable
class EgressPort(Port, Protocol):
    """Contract for transmitting telemetry payloads to external endpoints."""

    def send(self, payload: Mapping[str, Any]) -> None:
        """Transmit a payload to downstream consumers."""
        ...

    # Zero lifecycle hooks declared. Pure Discrete Sink Archetype.
```

### 5.5 Refactored `BaseAdapterRegistry[T]` (`src/services/registry/base.py`)

Parameterize the generic registry with `T = TypeVar("T", bound=Port)` and validate both driven adapter module locality and port pedigree:

```python
from domain.ports.base import Port

T = TypeVar("T", bound=Port)


class BaseAdapterRegistry(Generic[T]):
    ...

    def register(self, key: str, adapter: T) -> None:
        if not key or not isinstance(key, str):
            raise ValueError("Registry key must be a non-empty string.")
        if key in self._adapters:
            raise KeyError(f"Adapter with key '{key}' is already registered.")
        self._assert_driven_adapter(adapter)
        if not isinstance(adapter, Port):
            raise TypeError(f"Adapter must satisfy domain.ports.base.Port, got: {type(adapter).__name__}")
        self._adapters[key] = adapter
```

---

## 6. Verification Strategy & Test Matrix

| Test ID | Scope | Invariant / Specification | Verification Method |
| :--- | :--- | :--- | :--- |
| **TEST-PORT-01** | Unit | `Port` marker protocol hierarchy | Assert `issubclass(LifecyclePort, Port)`, `issubclass(WatcherPort, Port)`, and `issubclass(EgressPort, Port)`. |
| **TEST-PORT-02** | Unit | Active vs. Passive Discrimination | Assert `issubclass(WatcherPort, LifecyclePort)` and `not issubclass(EgressPort, LifecyclePort)`. |
| **TEST-PORT-03** | Unit | Concrete Driven Adapter Satisfaction | Assert `FileSystemWatcher` satisfies `(Port, LifecyclePort, WatcherPort)` and `NullTransmitter` satisfies `(Port, EgressPort)` but NOT `LifecyclePort`. |
| **TEST-PORT-04** | Unit | Registry Generic Bound Enforcement | Verify `BaseAdapterRegistry` rejects non-Port classes with `TypeError` and passes `mypy --strict`. |
| **TEST-PORT-05** | Unit | Policy L1, L2, L3 Behavioral Conformance | Verify `FileSystemWatcher` idempotency, bounded thread join on stop, and clean shutdown on mock errors. |

---

## 7. Phased Implementation Milestones

* **Milestone 1 (Design Documentation):**
  - Author and merge SDD-013 in `architecture/designs/`.
* **Milestone 2 (Protocol Construction):**
  - Implement `src/domain/ports/base.py`.
  - Refactor `src/domain/ports/watcher.py` and `src/domain/ports/egress.py`.
  - Update `src/domain/ports/__init__.py`.
* **Milestone 3 (Registry Alignment & Test Suite):**
  - Refactor `src/services/registry/base.py` (`T = TypeVar("T", bound=Port)`).
  - Implement `tests/unit/test_domain_ports.py`.
  - Verify all quality gates pass via `scripts/verify.py`.
