# Context & Developer Environment Guide: `ed-telemetry`

## 1. Project Overview & Architecture
`ed-telemetry` is a pure Hexagonal Architecture (Ports and Adapters) telemetry engine for *Elite Dangerous*, supporting Linux (Steam / Proton) and native Windows.

### Architectural Layout (`src/`)
- `src/domain/`: Pure domain core models, business entities, and boundary port protocols. Zero imports of infrastructure, presentation, or external frameworks.
- `src/domain/ports/`: Domain boundary ports and capability protocols:
  - `base.py`: Root `Port` marker protocol, `LifecyclePort`, `DiscreteSinkPort`, `StreamSourcePort`, `ConnectionPort`, `TransactionalPort`.
  - `watcher.py`: `WatcherPort` (composes `LifecyclePort` + `StreamSourcePort`).
  - `egress.py`: `EgressPort` (specializes `DiscreteSinkPort`).
- `src/services/`: Application services, DTO contracts, and driven adapter registries:
  - `services/registry/base.py`: `BaseAdapterRegistry[T]` bounded by `Port` with automated reflection enforcement.
  - `services/registry/watcher.py`: `WatcherRegistry` ($1 \rightarrow 1$ active source).
  - `services/registry/egress.py`: `EgressRegistry` ($1 \rightarrow N$ broadcast sinks).
  - `services/bootstrap.py`: Composition root staging adapters, registries, and services into `ApplicationContext`.
- `src/infrastructure/`: Driven adapters implementing domain ports (`infrastructure.watcher`, `infrastructure.egress`).
- `src/interfaces/`: Driving adapters (e.g. CLI entrypoint in `src/interfaces/cli.py`).

---

## 2. Python Virtual Environment & Tooling Paths

The project uses a local virtual environment located at `.venv/` in the repository root:

* **Python Interpreter:** `.venv/bin/python`
* **Pytest:** `.venv/bin/pytest`
* **Ruff (Linter & Formatter):** `.venv/bin/ruff`
* **Import Linter:** `.venv/bin/lint-imports`

> [!IMPORTANT]
> Always execute commands and tests directly using `.venv/bin/<tool>` (e.g. `.venv/bin/python scripts/verify.py` or `.venv/bin/pytest tests/unit/`).

---

## 3. Standard Verification Commands

All changes must pass Tier 2 Quality Gates before PR submission:

```bash
# 1. Complete Tier 2 Quality Gates (Ruff lint, Ruff format check, Pytest suite, CLI smoke test):
.venv/bin/python scripts/verify.py

# 2. Targeted Unit Tests:
.venv/bin/pytest tests/unit/test_domain_ports.py
.venv/bin/pytest tests/unit/test_adapter_registry.py

# 3. Import Boundary Linter (verifies Hexagonal isolation invariants):
.venv/bin/lint-imports

# 4. Local Wine Windows NT Simulation (optional/cross-platform):
./scripts/run_wine_tests.sh
```

---

## 4. Architectural Rules & Governance Invariants

Governed by repository ADRs (`architecture/adr/`) and SDDs (`architecture/designs/`):
1. **Invariant A (Domain Isolation):** `src/domain/` depends strictly on Python standard library typing constructs. Never import `services.*` or `infrastructure.*`.
2. **Invariant D (Downward Layering):** Infrastructure depends on Domain; Interfaces depend on Services; Services depend on Domain Ports.
3. **Invariant G (Infrastructure Isolation):** Services and ApplicationContext must never directly reference or import concrete classes from `src/infrastructure/`. Adapters must be injected via abstract Port contracts.
4. **Protocols with Properties:** In Python `typing.Protocol`, protocols defining non-method members (e.g., `@property def is_active(self) -> bool` on `LifecyclePort`) do not support `issubclass()`. In tests, assert protocol composition via MRO inspection (`LifecyclePort in WatcherPort.__mro__`) and instance validation (`isinstance(instance, LifecyclePort)`).
