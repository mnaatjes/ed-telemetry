---
title: "ADR 0020: Strict Ingestion Scope Boundary, Domain Agnosticism, and Anti-Creep Guardrails"
tags: ["adr", "governance", "boundaries", "scope", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0020: Strict Ingestion Scope Boundary, Domain Agnosticism, and Anti-Creep Guardrails

## Status
Accepted

## Context
EDMarketConnector, the historical desktop community tool for Elite Dangerous, accumulated architectural fragility by coupling file monitoring, game state parsing, desktop UI rendering (Tkinter), cloud uploading (EDDN, Inara, EDSM), and a third-party plugin ecosystem into a single monolith.

During the architectural evolution of `ed-telemetry`, preliminary explorations considered embedding a client SDK, plugin architecture, or higher-level game state aggregators. However, expanding scope into domain interpretation, cloud uploaders, or UI threatens to reproduce the failure modes of the legacy monolith.

`ed-telemetry` must serve one isolated operational mission: **authoritative, cross-platform file discovery, continuous change monitoring, raw byte extraction, and outbound stream transmission.**

## Decision

1. **Strict Ingestion Scope:**
   - The sole responsibility of `ed-telemetry` is accessing, monitoring, reading, and transmitting content from Elite Dangerous journal and snapshot files across Linux/Proton, Wine, and Windows.
   - All domain interpretation (commodity market calculations, outfitting analysis, trade routes), user interfaces, and external cloud integrations (EDDN, EDSM, Inara) are strictly excluded and delegated to downstream consumer applications.

2. **Retirement of Embedded Satellite SDK:**
   - Any requirement or design for an embedded "satellite SDK" or internal plugin system is permanently retired. Downstream consumers interact with `ed-telemetry` either via standard Python package imports (instantiating `build_container()`) or via external driving/driven network adapters (CLI, IPC, local socket).

3. **Domain Agnosticism (Raw Envelope Rule):**
   - Core boundary DTOs (`FileIngestionEventDTO`, `TelemetryPayloadDTO`) transport raw bytes, file hashes, timestamps, and path metadata. Core shall not declare game-semantic domain models (e.g., commodity pricing, ship module statistics).

4. **Automated Enforcement Guardrails:**
   - **Outbound HTTP Client Ban:** Forbid imports of `requests`, `httpx`, `aiohttp`, `urllib3` across the entire codebase to prevent cloud uploaders inside `ed-telemetry`. (Note: Inbound HTTP server frameworks for driving adapters remain permitted if needed).
   - **GUI Framework Ban:** Forbid imports of `tkinter`, `PyQt5`, `PyQt6`, `PySide6`, `textual`.
   - **Topology Invariant:** Enforce that `src/ed_telemetry/` contains strictly `core/`, `adapters/`, and `bootstrap/` (no `sdk/`, `plugins/`, or `ui/`).
   - Guardrails are enforced via `.importlinter` contracts and AST verification in `tests/architecture/test_boundaries.py`.

## Consequences
- The codebase remains lean, headless, fast, and completely immune to feature creep.
- Downstream projects (companion apps, web UIs, Discord bots) can depend on `ed-telemetry` without inheriting unwanted dependencies or UI luggage.
