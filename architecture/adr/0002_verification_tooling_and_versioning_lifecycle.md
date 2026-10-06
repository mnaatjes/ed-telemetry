---
title: "ADR 0002: Verification Tooling, Dependency Topology, and Release Versioning Lifecycle"
status: "accepted"
date: "2026-10-06"
tags: ["architecture", "adr", "tooling", "dependencies", "cicd", "versioning", "bump-my-version"]
---

# ADR 0002: Verification Tooling, Dependency Topology, and Release Versioning Lifecycle

## 1. Context and Problem Statement

To prevent architectural drift and dependency bloat in `ed-telemetry`, we require an authoritative decision governing:
1. **Dependency Topology:** How external production and development libraries are declared without file sprawl or synchronized `.txt` lists.
2. **Automated Verification Tooling Stack:** Which linters, type checkers, and architectural boundary validators are mandatory in Continuous Integration.
3. **Release & Versioning Lifecycle:** How version increments are tracked, bumped, and synchronized across documentation and package manifests.

---

## 2. Decision Drivers

* **Zero-Sprawl Packaging:** Eliminate fragmented `requirements*.txt` files; declare all dependencies in a single authoritative PEP 621 manifest (`pyproject.toml`).
* **Machine-Enforced Architecture:** Employ specialized linters in CI to guarantee that the invariants defined in [ADR 0001](0001_architectural_vision_and_operational_concept.md) are strictly upheld.
* **Deterministic Versioning:** Enforce semantic versioning via automated tooling (`bump-my-version`) across code and documentation.
* **Fast Developer Feedback:** Tooling execution in CI must complete rapidly across local environments and GitHub Actions.

---

## 3. Decision Outcome

Chosen Option: **PEP 621 Standard Dependencies, Dedicated CI Tooling Stack, and `bump-my-version` Semantic Lifecycle**.

---

## 4. Dependency Topology (Rejection of `requirements.txt`)

### 4.1 Prohibition of Flat Requirements Files
* **Policy:** The repository strictly prohibits the creation or use of `requirements.txt`, `requirements-dev.txt`, or any auxiliary text files for dependency specification.
* **Single Source of Truth:** All dependencies are declared exclusively in `pyproject.toml` using standard PEP 621 metadata.

### 4.2 Dependency Partitioning Scheme
* **Base Runtime (`dependencies`):** Restricted strictly to minimal, lightweight core libraries required for headless domain parsing and transmission (e.g. `pydantic`, `watchdog`, `httpx`).
* **Optional Feature Groups (`[project.optional-dependencies]`):**
  - `server`: Libraries required for network serving and AI integration (`fastapi`, `uvicorn`, `mcp`).
  - `dev`: Complete engineering toolchain (`pytest`, `ruff`, `mypy`, `import-linter`, `bump-my-version`).
* **Installation Workflows:**
  - Headless/CLI User: `pip install .`
  - Web/API User: `pip install .[server]`
  - Contributor/CI: `pip install -e .[dev,server]`

---

## 5. Mandatory Verification Tooling Stack

The CI pipeline executes four mandatory quality gates:

| Tool | Role in Verification Gate | Mandatory Rules Enforced |
| :--- | :--- | :--- |
| **`import-linter`** | **Architectural Boundary Gate** | Enforces the package import matrix and Invariants A & B from ADR 0001. Blocks circular loops, domain I/O leaks, and SDK leakage into production packages. |
| **`ruff`** | **Linting & Code Formatting** | Enforces PEP 8, import sorting (`I001`), bug detection (`B`), and modern Python 3.11+ syntax idioms. |
| **`mypy`** | **Type & Port Contract Gate** | Strict static type validation across `packages/`. Validates that concrete adapters strictly satisfy `ed_domain.ports` interfaces. |
| **`pytest`** | **Behavioral & Bootstrap Gate** | Executes headless unit tests (`tests/unit/`), integration workflows (`tests/integration/`), and side-effect-free bootstrap verification. |

---

## 6. Release Versioning Policy & `bump-my-version`

### 6.1 Semantic Versioning Lifecycle
* **Pre-Release Baseline:** Development begins at version `0.1.0`.
* **Milestone Progression:**
  - `0.1.x`: Initial Elaboration phase (scaffolding, walking skeleton, CI gates).
  - `0.2.0` – `0.9.x`: Construction phases (domain event models, watcher, egress transmitters, CLI/API/MCP adapters).
  - `1.0.0`: First production release ready for community deployment.

### 6.2 Authoritative Controlled Files
Version strings must be maintained in lockstep across four authoritative targets:
1. `pyproject.toml` (Project metadata `version = "X.Y.Z"`)
2. `packages/ed_domain/__init__.py` (Runtime inspectable `__version__ = "X.Y.Z"`)
3. `README.md` (Project header badge / version declaration)
4. `CHANGELOG.md` (Keep a Changelog release heading)

### 6.3 Tooling Configuration & Branch Restriction Gate
* **Tool:** `bump-my-version` configured under `[tool.bumpversion]` in `pyproject.toml`.
* **Branch Restriction Policy:** Running `bump-my-version` to create release tags is **strictly restricted to the `main` branch**. Releasing from feature or topic branches is prohibited to prevent stray tags and history divergence.
* **Execution:** Releases are cut via automated commands on `main` (e.g. `bump-my-version bump minor`), which update all four target files and generate signed git tags automatically.


---

## 7. Consequences

### Positive
* Zero dependency synchronization bugs between pip text files and package metadata.
* Architectural integrity is mathematically protected in CI via `import-linter`.
* Fast, unified formatting and linting via Rust-based `ruff`.
* Automated, error-free version bumps across code and documentation.

### Negative / Trade-Offs
* Developers must use PEP 621 pip install commands (`pip install -e .[dev]`).
* CI workflows must install the full `dev` toolchain to run verification gates.
