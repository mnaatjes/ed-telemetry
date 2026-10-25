---
title: "ADR 0024: Hexagonal CLI Driving Adapter Standards, Best Practices, and Enforcement"
tags: ["adr", "cli", "standards", "best-practices", "hexagonal", "governance"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0024: Hexagonal CLI Driving Adapter Standards, Best Practices, and Enforcement

## Status
Accepted

## Context
With the HTTP API, SQLite WAL persistence, and real-time streaming engine in place, `ed-telemetry` requires a standardized Command-Line Interface (CLI). Under Hexagonal Architecture, the CLI functions strictly as a **Driving (Inbound) Adapter**.

Without formal standards and boundaries, CLI adapters frequently suffer from:
1. **Business Logic Leaks:** Ingestion logic, directory scanning, or database queries embedded directly in command handlers.
2. **Framework Creep:** Heavy third-party CLI frameworks (`click`, `typer`, `rich`, `textual`) bloating dependencies and violating the ADR 0020 zero-dependency guardrail.
3. **Improper Exit Codes & Error Handling:** Raw tracebacks dumping onto stdout/stderr rather than clean POSIX exit codes and structured feedback.
4. **Poor Headless Daemon Support:** Missing direct command controls to start the HTTP/SSE daemon, inspect game state, or query historical events.

## Decision

### 1. Functional Scope of the CLI
The `ed-telemetry` CLI shall expose four primary subcommands:
1. `ed-telemetry serve`: Starts the long-running daemon (inbound file watcher, SQLite persistence, and HTTP/SSE server on configurable host/port).
2. `ed-telemetry status`: Queries current operational state (watcher running, active journal file, monitored path, queue size) and emits human-readable text or JSON.
3. `ed-telemetry status game`: Reads and displays live player cockpit status (`Status.json`) and flags.
4. `ed-telemetry events`: Queries recent historical events from the local SQLite persistence store with optional `--limit` and `--topic` filters.

### 2. Hexagonal CLI Architectural Rules & Best Practices

1. **Strict Driving Adapter Role (Zero Business Logic):**
   - The CLI adapter (`adapters/driving/cli/`) must act strictly as a thin protocol translator:
     - Parse terminal input (`sys.argv`).
     - Map flags to Use Case request DTOs.
     - Invoke driving port use-case interactors.
     - Format returned DTOs to standard console output (plain text or `--json`).
   - The CLI layer must **never** perform direct filesystem I/O, database queries, or socket management.

2. **Zero-Dependency Guardrail (Standard Library `argparse`):**
   - The CLI is implemented strictly with Python standard library `argparse` and `sys`.
   - Third-party CLI frameworks (`click`, `typer`, `docopt`, `rich`) are forbidden in `ed_telemetry` production dependencies.

3. **Inward-Only Dependencies:**
   - The CLI adapter imports only `core/ports/driving/`, `core/ports/dto/`, and the composition root `bootstrap/container.py` (via entrypoint `main()`).
   - Core layers know nothing about `argparse`, `sys.argv`, terminal formatting, or exit codes.

4. **POSIX Exit Code Semantics:**
   - `0`: Success.
   - `1`: Operational or runtime error (handled cleanly with clear message on stderr).
   - `2`: Command line syntax or argument parsing error (standard `argparse` exit).

5. **Machine & Human Friendly Formatting:**
   - Default output is clean, concise human text.
   - All query commands support a `--json` flag producing valid, unadorned JSON for piping to `jq` or downstream tools.

### 3. Automated Enforcement Matrix

| Gate | Tool / Check | Rule Enforced |
| :--- | :--- | :--- |
| **Architectural AST Tests** | `pytest tests/architecture/test_boundaries.py` | Forbids third-party CLI frameworks (`click`, `typer`, `rich`) and validates CLI adapter layer isolation. |
| **Import Linter Contracts** | `.importlinter` | Enforces `use_case_transport_isolation` and `composition_root_isolation`. |
| **Type Verification** | `mypy --strict` | Guarantees static type safety across all argument parsing and handler signatures. |
| **Wine Simulant Tests** | `scripts/run_wine_tests.sh` | Verifies `ed-telemetry` CLI subcommands (`serve`, `status`, `events`) under Windows NT / Wine environment. |
| **CI Matrix** | GitHub Actions (`verify.py`) | Executes linters, boundaries, and unit tests across Linux and Windows runners. |

### 4. Planned CLI Logging Features (Future Scope)
The following observability capabilities are planned for future iterations and accommodated in the CLI argument design:
1. **Live Event Tailing (`ed-telemetry tail` / `events --follow`):** Connects to `GetTelemetryStreamUseCase` to stream raw journal events live to stdout as they occur.
2. **Audit Diagnostics (`ed-telemetry logs audit`):** Inspects internal watcher lifecycle transitions (`WatcherAuditEventDTO`) including part rollovers, freshness checks, and line quarantining.
3. **Application Log Routing (`--log-level`, `--log-file`):** Standardized console and file logger configurations for debugging daemon runtime execution.

## Consequences
- The CLI provides an ergonomic, Unix-friendly interface for operators and shell scripts.
- The entire application remains 100% zero-dependency, adhering strictly to ADR 0020.
- All commands execute through tested use-case interactors, ensuring identical behavior between CLI and HTTP endpoints.
- Future logging and tailing capabilities are architecturally accommodated without premature implementation.
