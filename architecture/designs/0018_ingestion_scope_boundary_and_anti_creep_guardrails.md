---
title: "SDD-018: Ingestion Scope Boundary, Domain Agnosticism, and Anti-Creep Guardrails"
tags: ["sdd", "governance", "boundaries", "scope", "verification", "ast"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-018: Ingestion Scope Boundary, Domain Agnosticism, and Anti-Creep Guardrails

## 1. Executive Summary
This design document defines the structural contracts, AST checks, and Import Linter rules that enforce the strict scope boundaries established in ADR 0020. It prevents feature creep (UI frameworks, outbound cloud uploaders, plugin systems, and game business domain entities) through automated continuous verification.

## 2. Forbidden Dependencies Matrix

| Category | Forbidden Modules | Rationale |
| :--- | :--- | :--- |
| **Outbound HTTP Clients** | `requests`, `httpx`, `aiohttp`, `urllib3` | Cloud uploaders (EDDN, Inara, EDSM) must exist only in downstream consumer applications, not inside `ed-telemetry`. |
| **Desktop UI Frameworks** | `tkinter`, `PyQt5`, `PyQt6`, `PySide6`, `textual` | `ed-telemetry` is strictly a headless ingestion pipe and daemon. |
| **Embedded Plugin/SDK Trees** | Any directory named `sdk`, `plugins`, `ui`, `presentation` | Architecture must maintain strict 3-tier hexagonal root: `adapters`, `bootstrap`, `core`. |

## 3. Automated Guardrail Specifications

### 3.1 Import Linter Contract (`.importlinter`)
A new forbidden contract named `anti_creep_framework_isolation`:
- **Source Modules:** `ed_telemetry`
- **Forbidden Modules:** `requests`, `httpx`, `aiohttp`, `urllib3`, `tkinter`, `PyQt5`, `PyQt6`, `PySide6`, `textual`

### 3.2 Architectural Pytest Suite (`tests/architecture/test_boundaries.py`)
Four new automated AST invariants:
1. `test_no_outbound_http_client_libraries`:
   - Walks AST of all `.py` files under `src/ed_telemetry`.
   - Asserts zero occurrences of `requests`, `httpx`, `aiohttp`, `urllib3`.
2. `test_no_gui_framework_imports`:
   - Walks AST of all `.py` files under `src/ed_telemetry`.
   - Asserts zero occurrences of GUI framework imports (`tkinter`, `PyQt5`, `PyQt6`, `PySide6`, `textual`).
3. `test_package_topology_strictly_hexagonal`:
   - Validates that subdirectories of `src/ed_telemetry/` are strictly limited to `adapters`, `bootstrap`, and `core`.
   - Explicitly asserts absence of `sdk/`, `plugins/`, or `ui/`.
4. `test_core_ports_dto_remain_game_semantic_agnostic`:
   - Inspects dataclass definitions in `src/ed_telemetry/core/ports/dto/`.
   - Validates that names adhere to transport/envelope terminology (`Event`, `DTO`, `Snapshot`, `Payload`, `Result`, `Command`) and forbids game business entity identifiers (e.g., `Commodity`, `MarketOrder`, `TradeRoute`, `ShipFitting`).

## 4. Verification Strategy
- Execute `python scripts/verify.py` locally and in CI:
  - Pre-commit hygiene checks.
  - Import Linter verifying 6 contracts (including `anti_creep_framework_isolation`).
  - Mypy static typing across all source files.
  - Pytest executing all 113+ unit and architectural compliance tests.
