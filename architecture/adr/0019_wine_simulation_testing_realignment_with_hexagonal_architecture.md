---
title: "ADR 0019: Realignment of Wine Cross-Platform Simulation Testing with Standard Hexagonal Architecture"
tags: ["adr", "wine", "testing", "hexagonal", "verification"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0019: Realignment of Wine Cross-Platform Simulation Testing with Standard Hexagonal Architecture

## Status
Accepted

## Context
Following the hexagonal architecture refactor in ADR 0017 / SDD-015 and the expansion of query use cases in ADR 0018 / SDD-016:
- The package root was unified under `ed_telemetry/` with standard hexagonal layers (`adapters/`, `bootstrap/`, `core/ports/`, `core/use_cases/`).
- The legacy `infrastructure.*` and `services.*` module namespaces were retired.
- Boundary reflection verification (`tests.helpers.boundary_reflection`) was superseded by Import Linter and architectural boundary pytest suites.
- Ingestion query capabilities were expanded into 5 discrete use cases (`FindJournalPathUseCase`, `GetJournalFilesUseCase`, `GetLatestGameStatusUseCase`, `GetAuxiliarySnapshotUseCase`, `SubmitSnapshotRefreshUseCase`).

However, `scripts/run_wine_tests.sh` retained legacy import paths and assertions targeting retired packages, causing execution failure when verifying the Windows Python simulant under Wine.

## Decision
1. **Realine Module Imports:**
   - Update all watcher component imports to `ed_telemetry.adapters.driven.watcher.*`.
2. **Retire Legacy Service/Reflection Stages:**
   - Remove assertions referencing `services.bootstrap.build_application_context`, `services.watcher.WatcherService`, and `tests.helpers.boundary_reflection`.
3. **Introduce Hexagonal Windows Verification:**
   - Validate `ed_telemetry.bootstrap.container.Container` instantiation and DI wiring under Windows Python.
   - Validate direct driving invocation of the 5 telemetry query and hint use cases using Windows simulated file paths.
   - Verify boundary DTO immutability and serialization compatibility under Windows NT.

## Consequences
- `scripts/run_wine_tests.sh` remains a fully functioning gate for Windows runtime validation on Linux developer workstations.
- Verification covers both lower-level Windows filesystem watcher adapters and the driving hexagonal use case boundaries.
