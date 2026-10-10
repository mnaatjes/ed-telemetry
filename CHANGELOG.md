# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Runtime reflection boundary verification harness (`tests/helpers/boundary_reflection.py` and `tests/unit/test_boundary_reflection.py`) auditing memory graphs across four architectural junctions to detect and prevent transitive runtime object tunneling, governed by ADR 0013 and SDD-011.
- Driven Adapter Registry subsystem (`src/services/registry/`) implementing generic protocol `BaseAdapterRegistry[T]` with automated runtime driven adapter reflection enforcement (`_assert_driven_adapter`), governed by ADR 0014 and SDD-012.
- Specialized port-family registries: `WatcherRegistry` (managing $1 \rightarrow 1$ active input stream watcher sources) and `EgressRegistry` (managing $1 \rightarrow N$ outbound broadcast sinks).
- Composition root wiring (`src/services/bootstrap.py`) staging adapter instantiation, registry enrollment, and service injection while strictly shielding registries and concrete infrastructure adapters from `ApplicationContext`.
- Comprehensive unit test suite (`tests/unit/test_adapter_registry.py`) covering tests `TEST-REG-01` through `TEST-REG-05`.
- Diátaxis How-To runbooks: `docs/how-to/register_driven_adapter.md` (authoring and registering driven adapters) and `docs/how-to/create_driven_adapter_registry.md` (creating new port-family registries).

## [0.3.0] - 2026-10-09

### Changed
- Refactored entire codebase topology from legacy flat `packages/` monorepo to Pure Hexagonal `src/` layout (`src/{domain,services,infrastructure,interfaces}`) and satellite `sdk/` governed by ADR 0012 and SDD-010.
- Migrated namespaces: `ed_domain` -> `domain`, `ed_services`/`ed_app` -> `services`, `ed_watcher` -> `infrastructure.watcher`, `ed_egress` -> `infrastructure.egress`, `ed_cli` -> `interfaces.cli`, `ed_sdk` -> `sdk`.
- Reconfigured single-package discovery in `pyproject.toml` (`where = ["src"]`) and updated entrypoints and import-linter boundary contracts.
- Updated all verification harnesses (`scripts/verify.py`, `scripts/run_wine_tests.sh`, `scripts/print_dependency_graph.py`) to target the Pure Hexagonal topology.
- Formally superseded layout sections of ADR 0001 and ADR 0002 with ADR 0012.

### Added
- Architectural research on Frontier Developments telemetry file specifications (`architecture/research/journal_and_snapshot_filename_spec.md`) documenting canonical regex patterns, Horizons/Odyssey naming variances, and part rollover semantics.
- Telemetry metadata specification (`architecture/research/target_files_metadata_spec.md`) detailing software/build context (`Fileheader`), account identification (`Commander.FID`), and snapshot envelope attributes.
- Reference implementation analysis of EDMarketConnector (`architecture/notes/edmarketconnector_journal_analysis.md`) analyzing journal discovery, JSONL stream consumption, and read-only file semantics.
- Pre-ADR architectural planning document (`architecture/notes/pre_adr_file_presence_freshness_detection.md`) defining the File Presence & Freshness Detection (FPFD) phase, unified hybrid event drivers, and consolidated `FileIngestionEvent` / `WatcherAuditEvent` models.
- Native dual-OS GitHub Actions CI workflow executing `scripts/verify.py` against both `ubuntu-latest` and `windows-latest` across Python 3.11 and 3.12 (ADR 0005).
- Binary ABI memory validation test suite (`tests/unit/test_windows_simulant.py`) verifying Microsoft Win32 GUID memory struct alignment and `FOLDERID_SavedGames` byte literal fidelity on Linux.
- Local Wine simulation environment setup script (`scripts/setup_wine_simulant.sh`) provisioning isolated prefix (`.cache/winepfx/`) with official Windows Python 3.11 embeddable package without root privilege.
- Wine test launcher (`scripts/run_wine_tests.sh`) executing Windows path discovery strategies under native Windows Python via Wine.
- Diátaxis How-To developer runbook (`docs/how-to/test_cross_platform_locally.md`) detailing cross-platform verification and Wine simulation procedures.
- Active journal candidate selection and sorting engine (`packages/ed_watcher/selector.py`) implementing lexicographical sorting, part rollover ordering, and stream positioning modes (`StreamPosition`, `JournalCandidate`, `JournalSelector`) governed by ADR 0006 and SDD-004.
- Use case specification for stream positioning and ingestion modes (`architecture/use-cases/0003_stream_positioning_and_ingestion_modes.md`) and Diátaxis Reference guide (`docs/reference/watcher_journal_selector.md`).
- Status and auxiliary snapshot file identification subsystem (`packages/ed_watcher/snapshots/`) providing canonical snapshot definitions, case-normalization lookups, and registry tracking (`SnapshotCandidate`, `SnapshotRegistry`, `SnapshotIdentifier`) governed by ADR 0007 and SDD-005.
- Diátaxis Reference documentation for snapshot identification and casing normalization (`docs/reference/watcher_snapshot_identifier.md`).
- Unified file ingestion engine, reactive reactor loop, and audit telemetry system (`packages/ed_watcher/engine/`) implementing non-blocking streaming (`JournalTailer`), zero-byte atomic truncation guards (`SnapshotReader`), and hybrid inotify/fallback ticker scheduling (`WatcherReactor`, `WatcherIngestReceiver`) governed by ADR 0008 and SDD-006.
- Ingestion telemetry models (`FileIngestionEvent`, `WatcherAuditEvent`, `FileKind`, `WatcherAuditAction`) and stream state context (`JournalStreamContext`, `SnapshotFreshnessTracker`).
- Diátaxis Reference documentation for watcher engine and reactor loop (`docs/reference/watcher_engine.md`).
- Extended Wine Windows NT test suite (`scripts/run_wine_tests.sh`) covering path discovery, journal selection, snapshot identification, and reactive ingestion engine execution.
- Formal driving port protocol contract (`packages/ed_domain/ports/watcher.py`) adding `register_event_handler`, `register_audit_handler`, and handler callable types (`IngestionEventHandler`, `AuditEventHandler`) governed by ADR 0009 and SDD-007.
- Concrete driving adapter implementation (`packages/ed_watcher/watcher.py`) with `FileSystemWatcher` managing background daemon worker threads, auto-discovery path resolution, exception shielding, and deterministic join on shutdown.
- Updated composition root (`packages/ed_app/bootstrap.py`) wiring `FileSystemWatcher` into `TelemetryEngine`.
- Comprehensive unit test suite (`tests/unit/test_watcher_adapter.py`) and Windows NT Wine runner test step verifying asynchronous watcher dispatch and thread lifecycle.
- Diátaxis Reference documentation for `FileSystemWatcher` (`docs/reference/watcher_filesystem_adapter.md`).
- Developer integration guide with copy-pasteable runnable code patterns (`architecture/notes/watcher_developer_integration_guide.md`).
- Application Service Layer architecture, base protocols, and boundary invariants (`packages/ed_app/`) implementing pure `DataTransferObject` protocol, `BaseApplicationService` protocol, `ApplicationContext` container, and `ApplicationServiceError` hierarchy governed by ADR 0010 and SDD-008.
- Boundary enforcement contracts via `import-linter`: Invariant G (infrastructure adapter isolation forbidding driving surfaces and services from importing `ed_watcher`/`ed_egress`), Invariant D (downward layering), and Invariant C (protocol neutrality).
- Diátaxis Reference documentation for application scaffolding (`docs/reference/application_scaffolding.md`) and Diátaxis How-To developer runbook (`docs/how-to/add_application_service.md`).
- Onboarded `WatcherService` (`packages/ed_app/services/watcher.py`) and `WatcherStatusDTO` (`packages/ed_app/dto/watcher.py`) to the Application Service Layer, exposing watcher state and lifecycle through `WatcherPort` without adapter coupling governed by ADR 0011 and SDD-009.
- Updated `build_application_context()` composition root in `packages/ed_app/bootstrap.py` wiring `WatcherService` into `ApplicationContext`.
- Extended test suites (`tests/unit/test_application_scaffolding.py`, `tests/unit/test_watcher_service.py`) and Wine Windows runner (`scripts/run_wine_tests.sh`) validating side-effect-free context construction and watcher service execution under Windows NT.


## [0.2.0] - 2026-10-06

### Added
- Architectural baseline and modular monorepo package scaffolding under `packages/` (`ed_domain`, `ed_watcher`, `ed_egress`, `ed_sdk`, `ed_app`).
- Machine-enforced boundary contracts: Invariant A (Domain I/O purity), Invariant B (SDK runtime isolation), and layered dependencies via `import-linter`.
- Composition root bootstrapper (`packages/ed_app/bootstrap.py`) providing side-effect-free engine assembly.
- Minimal walking skeleton stubs for `WatcherPort`, `EgressPort`, `TelemetryEngine`, and CLI smoke test runner.
- Two-tier verification pipeline: Tier 1 (`pre-commit` local git hooks) and Tier 2 (`scripts/verify.py` and GitHub Actions CI matrix for Python 3.11 and 3.12).
- Release lifecycle protection hook (`scripts/guard_release_branch.py`) restricting `bump-my-version` execution strictly to the `main` branch.
- On-demand AST dependency and boundary graph inspector (`scripts/print_dependency_graph.py`) using `grimp`.
- Diátaxis How-To developer guide for local verification, automated testing, and AST graph inspection.
