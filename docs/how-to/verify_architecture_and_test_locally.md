---
title: "How to Verify Architecture and Run Tests Locally"
tags: ["how-to", "testing", "verification", "pre-commit", "ci", "developer-guide"]
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# How to Verify Architecture and Run Tests Locally

This guide details how to install and execute the full verification toolchain locally on your development workstation, ensuring clean commits and pre-empting Continuous Integration failures.

---

## 1. Prerequisites

Ensure you have Python 3.11 or newer installed, a virtual environment active, and the development toolchain installed in editable mode:

```bash
# From repository root
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 2. Set Up and Run Pre-Commit Hooks (Tier 1)

`pre-commit` enforces fast code formatting, linting, and syntax hygiene before any commit is created.

### 2.1 Install Git Hooks
Register the hooks with your local `.git` directory:

```bash
pre-commit install
```

Once installed, `pre-commit` runs automatically on staged files whenever you execute `git commit`.

### 2.2 Run Pre-Commit Manually Across All Files
To run formatting and linting across the entire repository on demand:

```bash
pre-commit run --all-files
```

---

## 3. Run Authoritative Quality Gates Locally (Tier 2)

The static type checker (`mypy`), architectural boundary validator (`import-linter`), unit test suite (`pytest`), and smoke test runner are intentionally omitted from `pre-commit` to prevent commit latency. Run these checks manually before pushing code.

### 3.1 Run Static Type Checking (`mypy`)
Verify that all packages and stub adapters strictly adhere to type annotations and Port contracts:

```bash
mypy
```

Expected output:
```text
Success: no issues found in 16 source files
```

### 3.2 Verify Architectural Boundaries (`import-linter`)
Ensure that Invariant A (Domain I/O purity), Invariant B (SDK runtime isolation), and layered dependencies remain unviolated:

```bash
lint-imports
```

Expected output:
```text
---------
Contracts
---------

Analyzed 20 files, 25 dependencies.
-----------------------------------

Invariant A: Domain package must remain purely decoupled KEPT
Invariant B: SDK forbidden in production packages KEPT
Layered Architecture Boundaries KEPT

Contracts: 3 kept, 0 broken.
```

### 3.3 Run Unit Tests (`pytest`)
Execute the headless test suite:

```bash
pytest -v
```

Expected output:
```text
============================= test session starts ==============================
...
tests/unit/test_bootstrap.py::test_build_engine_instantiation PASSED     [ 50%]
tests/unit/test_bootstrap.py::test_engine_lifecycle_smoke PASSED         [100%]

============================== 2 passed in 0.04s ===============================
```

### 3.4 Execute CLI Smoke Test
Confirm that the Composition Root boots and shuts down with zero display shims and zero side effects:

```bash
python -m ed_app
```

Expected output:
```text
ed-telemetry baseline verified: engine started successfully
```

---

## 4. Run the Full Quality Gate Suite in One Command (Preferred)

The canonical way to execute all Tier 2 quality gates locally—mirroring continuous integration identically across Linux, macOS, and native Windows—is via the orchestrator script:

```bash
python scripts/verify.py
```

Expected output:
```text
============================================================
Executing Tier 2 Quality Gates
============================================================

[RUNNING] Ruff Lint...
...
[PASSED] Ruff Lint

[RUNNING] Ruff Format Check...
...
[PASSED] Ruff Format Check

[RUNNING] Mypy Static Typing...
...
[PASSED] Mypy Static Typing

[RUNNING] Import Linter Boundaries...
...
[PASSED] Import Linter Boundaries

[RUNNING] Pytest Suite...
...
[PASSED] Pytest Suite

[RUNNING] CLI Smoke Test...
ed-telemetry baseline verified: engine started successfully
[PASSED] CLI Smoke Test

============================================================
All Tier 2 Quality Gates Passed Successfully!
============================================================
```

### 4.1 Manual Chained Invocation (Alternative)
If preferred, you can also execute the individual commands chained together in a POSIX shell:

```bash
ruff check packages tests && \
ruff format --check packages tests && \
mypy && \
lint-imports && \
pytest -v && \
python -m ed_app
```

---

## 5. Inspect the Live AST Dependency Graph On Demand

To visually inspect the actual import graph and verify boundary health without committing static graph dumps to git:

```bash
python scripts/print_dependency_graph.py
```

Expected output:
```text
=================================================================
Live AST Dependency & Boundary Graph (grimp)
=================================================================

[Package Cross-Boundary Imports]:
  ed_domain    ──► (none / pure isolation)
  ed_watcher   ──► (none / pure isolation)
  ed_egress    ──► (none / pure isolation)
  ed_sdk       ──► (none / pure isolation)
  ed_app       ──► [ed_domain, ed_egress, ed_watcher]

[Detailed Module-Level Import Pairs]:
  ed_app.__main__ ──► ed_app.cli.main
  ed_app.bootstrap ──► ed_domain.engine
  ed_app.bootstrap ──► ed_egress.transmitter
  ed_app.bootstrap ──► ed_watcher.watcher
  ...

=================================================================
Boundary Health Check:
  [OK] Invariant A: 'ed_domain' imports zero sibling packages.
  [OK] Invariant B: 'ed_sdk' is NOT imported by any runtime package.
=================================================================
```
