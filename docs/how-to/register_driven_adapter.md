---
title: "How to Register a Driven Adapter"
tags: ["how-to", "runbooks", "adapters", "infrastructure", "registry", "composition-root"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# How to Register a Driven Adapter

This runbook guides engineers through authoring and registering a concrete Driven Adapter within `ed-telemetry`. Governed by [ADR 0014](../../architecture/adr/0014_driven_adapter_registry_architecture_and_composition_root.md) and [SDD-012](../../architecture/designs/0012_driven_adapter_registry_and_composition_root.md).

---

## 1. Prerequisites

Before registering an adapter:
1. An abstract domain port protocol must exist in `src/domain/ports/` (e.g. `domain.ports.egress.EgressPort` or `domain.ports.watcher.WatcherPort`).
2. The adapter being registered must be a **Driven (Secondary) Adapter** designed for outward I/O (network sinks, disk persistence, or OS journal watchers).
3. **Driving Adapters** (CLI, REST endpoints, MCP tools) live in `src/interfaces/` and are **strictly prohibited** from adapter registries.

---

## 2. Standard Operating Procedure

Follow this 5-step checklist sequentially:

### Step 1: Implement the Abstract Domain Port in `src/infrastructure/`

Author your adapter in `src/infrastructure/<subsystem>/`:

```python
# src/infrastructure/egress/eddn.py
from collections.abc import Mapping
from typing import Any

from domain.ports.egress import EgressPort


class EddnTransmitter:
    """Outbound transmitter dispatching telemetry events to the EDDN relay network."""

    def __init__(self, endpoint_url: str = "https://eddn.edcd.io:4430/upload/") -> None:
        self.endpoint_url = endpoint_url

    def send(self, payload: Mapping[str, Any]) -> None:
        """Transmit payload to EDDN."""
        # Implementation of HTTP/ZMQ transmission...
        pass
```

> [!IMPORTANT]
> The adapter class module path MUST begin with `infrastructure.`. Any adapter originating from `domain.*`, `interfaces.*`, or `services.*` will be mathematically rejected by the registry's automated boundary reflection validator.

---

### Step 2: Export the Adapter from Infrastructure Subsystem

Add your new adapter to the appropriate `__init__.py` and `__all__`:

```python
# src/infrastructure/egress/__init__.py
from infrastructure.egress.eddn import EddnTransmitter
from infrastructure.egress.transmitter import NullTransmitter

__all__ = [
    "EddnTransmitter",
    "NullTransmitter",
]
```

---

### Step 3: Register the Adapter in the Composition Root (`src/services/bootstrap.py`)

In `src/services/bootstrap.py`, instantiate the adapter and register it into the appropriate port-family registry:

```python
# src/services/bootstrap.py
from infrastructure.egress.eddn import EddnTransmitter
from infrastructure.egress.transmitter import NullTransmitter
from services.registry.egress import EgressRegistry


def build_engine(journal_dir: Path | None = None) -> TelemetryEngine:
    # 1. Instantiate concrete driven adapters
    null_transmitter = NullTransmitter()
    eddn_transmitter = EddnTransmitter()

    # 2. Populate driven adapter registry
    egress_registry = EgressRegistry()
    egress_registry.register("null_transmitter", null_transmitter)
    egress_registry.register("eddn_transmitter", eddn_transmitter)

    # 3. Wire into engine / services
    ...
```

---

### Step 4: Write Unit Tests

Author unit tests verifying port protocol compliance and registration behavior in `tests/unit/`:

```python
# tests/unit/test_eddn_adapter.py
from domain.ports.egress import EgressPort
from infrastructure.egress.eddn import EddnTransmitter
from services.registry.egress import EgressRegistry


def test_eddn_transmitter_satisfies_port_protocol():
    transmitter = EddnTransmitter()
    assert isinstance(transmitter, EgressPort)


def test_eddn_transmitter_enrolls_in_registry():
    registry = EgressRegistry()
    transmitter = EddnTransmitter()
    registry.register("eddn", transmitter)
    assert registry.get("eddn") is transmitter
    assert transmitter in registry.get_transmitters()
```

---

### Step 5: Verify Quality Gates Locally

Run the verification pipeline to ensure that `import-linter`, `mypy`, runtime reflection tests, and unit tests pass:

```bash
.venv/bin/python scripts/verify.py
```
