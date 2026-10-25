---
title: "ADR 0026: Documentation Realignment with Diataxis Framework and SDK Retirement"
tags: ["adr", "documentation", "diataxis", "topology", "sdk", "cli", "logging"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0026: Documentation Realignment with Diataxis Framework and SDK Retirement

## 1. Context and Problem Statement

Following the pure hexagonal architecture refactor (ADR 0017), the introduction of SQLite event persistence and HTTP API streaming (ADR 0022, ADR 0023), zero-framework CLI commands (ADR 0024), and diagnostic logging infrastructure (ADR 0025), significant documentation divergence exists:
1. **Defunct Subsystem Documentation:** The `docs/` tree retains legacy runbooks and references describing a pre-hexagonal application service layer (`src/services/`, `ApplicationContext`, `BaseAdapterRegistry`) that was superseded by use-case interactors and the pure hexagonal package layout.
2. **Obsolete Root Architecture & File Topology:** `README.md` documents a deprecated 4-tier tree (`src/{domain,services,infrastructure,interfaces}`) and references the `sdk/` directory.
3. **Defunct `sdk/` Satellite Directory:** The `sdk/` directory contained only an abandoned `mock_writer.py` stub that has been superseded by tests in `tests/doubles/` and `tests/unit/`.
4. **Missing Operator & Integrator Runbooks:** The newly delivered CLI subcommands (`serve`, `status`, `events`, `logs`, `tail`), HTTP/SSE endpoints, local rotating file log locations, and real-time audit event bubbling have no Diátaxis how-to guides or API references.

## 2. Decision Drivers

* **Diátaxis Framework Compliance:** Rule 5.1 mandates strict adherence to the 4-quadrant Diátaxis framework (`tutorials/`, `how-to/`, `reference/`, `explanation/`) under `docs/`.
* **Zero Conceptual Drift:** Developer and operator documentation must accurately reflect the executable reality of the codebase at release `v0.4.0`.
* **Clean Workspace Topology:** Remove dead code and unused directories (`sdk/`) to eliminate cognitive load and linting noise.
* **Operator Usability:** Clear, task-oriented runbooks must exist for running the daemon, querying logs, tailing events, and consuming the HTTP API.

## 3. Considered Options

* **Option 1 (Ad-hoc Update):** Edit existing how-to files individually without retiring obsolete guides or restructuring the reference quadrant.
* **Option 2 (Comprehensive Diátaxis Realignment & SDK Pruning):** Formally retire obsolete application-service guides, purge `sdk/`, align `README.md` with `src/ed_telemetry/`, and author task-oriented How-To guides and authoritative Technical References covering CLI, HTTP API, and diagnostic logging.

## 4. Decision Outcome

Chosen Option: **Option 2 (Comprehensive Diátaxis Realignment & SDK Pruning)**.

### Consequences

* **Positive:**
  * `docs/how-to/` provides immediately actionable guides for operators to run `ed-telemetry`, inspect logs on Windows and Linux, and consume live telemetry over HTTP/SSE.
  * `docs/reference/` provides authoritative catalogs for CLI commands, REST/SSE endpoints, and diagnostic log storage.
  * `README.md` accurately depicts the pure hexagonal layout (`src/ed_telemetry/{core,adapters,bootstrap}`) matching release `v0.4.0`.
  * The deprecated `sdk/` directory is permanently removed.
* **Negative / Trade-offs:**
  * Requires authoring multiple comprehensive Markdown documents across `docs/how-to/` and `docs/reference/`.

## 5. Architectural Invariants

* **Invariant 1 (Hexagonal Namespace Integrity):** All documentation must reference canonical namespaces under `ed_telemetry.core.*`, `ed_telemetry.adapters.*`, and `ed_telemetry.bootstrap.*`.
* **Invariant 2 (Diátaxis Boundaries):** How-to guides must remain task-oriented step-by-step runbooks; reference documents must remain factual, structured API descriptions.
* **Invariant 3 (Metadata Frontmatter):** Every Markdown file in `docs/` must begin with standard YAML frontmatter declaring `title`, `tags`, `created_at`, and `last_updated_at`.
