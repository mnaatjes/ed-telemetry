---
title: "How to Create a Driven Adapter Registry"
tags: ["how-to", "runbooks", "registry", "adapters", "architecture", "services"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# How to Create a Driven Adapter Registry

This runbook guides engineers through authoring a new bespoke Port-Family Driven Adapter Registry within `src/services/registry/` in `ed-telemetry`. Governed by [ADR 0014](../../architecture/adr/0014_driven_adapter_registry_architecture_and_composition_root.md) and [SDD-012](../../architecture/designs/0012_driven_adapter_registry_and_composition_root.md).

---

## 1. Prerequisites

Before creating a new adapter registry:
1. A distinct domain port family must exist in `src/domain/ports/` (e.g. `domain.ports.storage.StoragePort` or `domain.ports.audio.AudioPort`).
2. The port family must have clear cardinality and dispatch semantics:
   - $1 \rightarrow N$: Broadcast dispatch across all registered sinks (e.g. `EgressRegistry`).
   - $1 \rightarrow 1$: Designated active instance with fallback or switching (e.g. `WatcherRegistry`).

---

## 2. Standard Operating Procedure

Follow this 6-step checklist sequentially:

### Step 1: Subclass `BaseAdapterRegistry[T]`

Create a new registry module in `src/services/registry/<port_name>.py`:

```python
# src/services/registry/storage.py
from __future__ import annotations

from collections.abc import Sequence

from domain.ports.storage import StoragePort
from services.registry.base import BaseAdapterRegistry


class StorageRegistry(BaseAdapterRegistry[StoragePort]):
    """Registry managing persistent storage driven adapters."""

    def get_primary_storage(self) -> StoragePort:
        """Return the default storage adapter."""
        return self.get("primary_storage")
```

> [!NOTE]
> `BaseAdapterRegistry[T]` automatically provides standard container mechanics (`register`, `get`, `get_all`, `list_keys`, `len`, `in`, `iter`) and validates that any registered adapter originates from `src/infrastructure/` via `_assert_driven_adapter`.

---

### Step 2: Implement Port-Family Specific Dispatch & Cardinality

Add specialized methods suited to the family's operational model (e.g. broadcast, fallback cascades, or active item selection):

```python
    def persist_across_all(self, record_id: str, data: bytes) -> None:
        """Persist data redundantly across all registered storage backends."""
        for backend in self.get_all():
            backend.save(record_id, data)
```

---

### Step 3: Export from `src/services/registry/__init__.py`

Update `src/services/registry/__init__.py` to export the new registry class:

```python
# src/services/registry/__init__.py
from services.registry.base import BaseAdapterRegistry
from services.registry.egress import EgressRegistry
from services.registry.storage import StorageRegistry
from services.registry.watcher import WatcherRegistry

__all__ = [
    "BaseAdapterRegistry",
    "EgressRegistry",
    "StorageRegistry",
    "WatcherRegistry",
]
```

---

### Step 4: Wire into the Composition Root (`src/services/bootstrap.py`)

In `src/services/bootstrap.py`, instantiate and populate your registry:

```python
# src/services/bootstrap.py
from infrastructure.storage.sqlite import SqliteStorage
from services.registry.storage import StorageRegistry


def build_application_context(...) -> ApplicationContext:
    # 1. Instantiate concrete adapters
    sqlite_adapter = SqliteStorage(...)

    # 2. Populate registry
    storage_registry = StorageRegistry()
    storage_registry.register("primary_storage", sqlite_adapter)

    # 3. Inject registry into consuming Application Services
    ...
```

---

### Step 5: Author Unit Tests

Create unit tests in `tests/unit/test_adapter_registry.py` verifying:
1. Rejection of non-infrastructure classes (inherited from `BaseAdapterRegistry`).
2. Correct generic typing and retrieval.
3. Family-specific cardinality and dispatch behavior.

---

### Step 6: Verify Quality Gates Locally

Execute the verification pipeline:

```bash
.venv/bin/python scripts/verify.py
```
