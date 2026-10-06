---
title: "ADR 0003: Minimal Walking Skeleton and Bootstrap Verification Contract"
status: "accepted"
date: "2026-10-06"
tags: ["architecture", "adr", "skeleton", "bootstrap", "ports", "elaboration"]
---

# ADR 0003: Minimal Walking Skeleton and Bootstrap Verification Contract

## 1. Context and Problem Statement

To complete the Unified Process Elaboration phase without premature feature bloat or "black-box" implementations, we must prove the validity of the architecture baseline, package boundaries, and composition root bootstrapper.

If we attempt to implement real Elite Dangerous journal parsing, Pydantic models, or network transmitters right now, we risk writing speculative code that has not been properly planned or approved. Conversely, if we leave packages completely empty, `import-linter` and CI bootstrap tests have nothing to verify.

We need a formal decision defining the **absolute minimal stub contracts** required to establish and verify the walking skeleton.

---

## 2. Decision Drivers

* **Anti-Bloat Principle:** Zero premature business logic, zero speculative event schemas, zero external API endpoints.
* **Deterministic Verification:** Provide just enough code so that `import-linter`, `mypy`, and `pytest` can mathematically prove that:
  1. `ed_domain` has zero dependencies and defines abstract ports.
  2. `ed_watcher` and `ed_egress` implement those ports without importing each other.
  3. `ed_app/bootstrap.py` can wire them together into an engine without runtime side-effects.
* **Reviewability:** Ensure the initial code footprint is transparent, small (< 100 lines total across all packages), and completely understandable.

---

## 3. Decision Outcome

Chosen Option: **Minimal Stub Walking Skeleton with Side-Effect-Free Composition Root**.

### 3.1 Minimal Stub Port Interfaces (`packages/ed_domain/ports/`)
To test polymorphism and dependency inversion without domain bloat, define minimal abstract protocols:

```python
# packages/ed_domain/ports/watcher.py
from abc import ABC, abstractmethod

class WatcherPort(ABC):
    @abstractmethod
    def start(self) -> None: ...
    @abstractmethod
    def stop(self) -> None: ...
```

```python
# packages/ed_domain/ports/egress.py
from abc import ABC, abstractmethod

class EgressPort(ABC):
    @abstractmethod
    def transmit(self, payload: dict) -> bool: ...
```

### 3.2 Minimal Core Engine (`packages/ed_domain/engine.py`)
```python
# packages/ed_domain/engine.py
from ed_domain.ports.watcher import WatcherPort
from ed_domain.ports.egress import EgressPort

class TelemetryEngine:
    def __init__(self, watcher: WatcherPort, transmitters: list[EgressPort]) -> None:
        self.watcher = watcher
        self.transmitters = transmitters
        self.is_running = False

    def start(self) -> None:
        self.is_running = True
        self.watcher.start()

    def stop(self) -> None:
        self.is_running = False
        self.watcher.stop()
```

### 3.3 Minimal Concrete Stubs (`ed_watcher` & `ed_egress`)
* `packages/ed_watcher/watcher.py`: Defines stub `JournalWatcher(WatcherPort)` with empty `start()` and `stop()` methods.
* `packages/ed_egress/transmitter.py`: Defines stub `NullTransmitter(EgressPort)` with `transmit() -> True`.

### 3.4 Composition Root Factory (`packages/ed_app/bootstrap.py`)
```python
# packages/ed_app/bootstrap.py
from ed_domain.engine import TelemetryEngine
from ed_watcher.watcher import JournalWatcher
from ed_egress.transmitter import NullTransmitter

def build_engine() -> TelemetryEngine:
    """Composition Root: Wires stub adapters into the core engine."""
    watcher = JournalWatcher()
    transmitters = [NullTransmitter()]
    return TelemetryEngine(watcher=watcher, transmitters=transmitters)
```

---

## 4. Verification Gate Contract

This minimal skeleton is deemed successful when:
1. `import-linter` validates that all import directions match ADR 0001.
2. `pytest tests/unit/test_bootstrap.py` asserts that `build_engine()` constructs a valid `TelemetryEngine` without spawning background threads or network calls.
3. `mypy` verifies type correctness across all packages with zero warnings.

---

## 5. Consequences

### Positive
* Zero cognitive overload: every file has under 20 lines of obvious code.
* No black boxes or unapproved algorithms.
* CI and boundaries are 100% verified before any real feature work begins.

### Negative / Trade-Offs
* Feature work is deferred until the skeleton and CI gates are verified and merged.
