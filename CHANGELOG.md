# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Dynamic credential hot-reloading via cached file `mtime` watch (`DynamicCredentialProvider`) allowing zero-downtime key rotation (`auth keygen --force`) without daemon restart (ADR 0033, #89).
- Added `--api-key` argument to `ed-telemetry stream` and `ed-telemetry tail` subparsers for explicit token passing (#90).
- Actionable interactive shell activation guidance (`source ~/.bashrc` or `export ED_API_KEY="..."`) on `ed-telemetry auth keygen --register-env` (#91).



## [0.6.4] - 2026-10-27

### Fixed
- Injected resolved API key credentials into outbound HTTP daemon requests (`stream`, `status`, `logs`) and improved HTTP error diagnostics (ADR 0029, #87).

## [0.6.3] - 2026-10-27

### Added
- Non-loopback network binding authentication enforcement failing fast on startup (code 1) when `--host` is bound to external or unspecified interfaces (`0.0.0.0`, LAN IPs) without an API key (ADR 0032, SDD-030, #83).
- Added `--allow-insecure` flag to `ed-telemetry serve` permitting explicit unauthenticated non-loopback operation with prominent console security warnings (ADR 0032, SDD-030, #83).
- Root CLI `-v` and `--version` flags resolving installed package version via standard library `argparse` `action="version"` (ADR 0031, SDD-029, #84).
- Actionable credential generation guidance when `ed-telemetry auth show` is invoked in unauthenticated mode across both human console text and `--json` outputs (ADR 0031, SDD-029, #84).

## [0.6.2] - 2026-10-26

### Added
- Resource starvation guardrails clamping `?limit=` parameters to `[1, 500]` on `/api/v1/events` and `/api/v1/diagnostics/logs` (ADR 0030, SDD-028, #78).
- Atomic SSE connection throttling (`max_sse_clients = 16`) on `/api/v1/stream` returning `HTTP 429 Too Many Requests` (RFC 7807 problem details) when client connection ceiling is exceeded (ADR 0030, SDD-028, #78).

### Documentation
- Updated `architecture/research/journal_and_snapshot_filename_spec.md` to include `ShipLocker.json` in Section 3.1 inventory table and Section 5.2 membership set (#76).

## [0.6.1] - 2026-10-26

### Added
- Local storage permissions hardening enforcing POSIX `0700` directory and `0600` file permissions on `telemetry.db` and rotating application logs (ADR 0029, SDD-027, #77).
- Perimeter Network Guarding enforcing pre-shared API keys via constant-time verification (`hmac.compare_digest`) across Bearer header, `X-API-Key`, and query parameters (ADR 0029, SDD-027, #77).
- Strict CORS governance replacing wildcard `*` with configurable allowed origins and `OPTIONS` preflight handling (ADR 0029, SDD-027, #77).
- CLI `auth` subcommands (`keygen`, `show`, `revoke`) with CSPRNG token standard (`ed_sec_<48-hex-chars>`) and automatic environment registration for Linux shell rc and Windows user environment (ADR 0029, SDD-027, #77).
- Operating system host path sanitization masking user home directories (`~`) in serialized API responses (ADR 0029, SDD-027, #77).
- Automated boundary leak detection test scanning source files against API token patterns (ADR 0029, SDD-027).


## [0.6.0] - 2026-10-26

### Added
- Added `stream` as canonical CLI driving adapter subcommand for continuous SSE domain event feed (`/api/v1/stream`), while retaining `tail` as backwards-compatible alias (ADR 0028, SDD-026).
- Added `-f` / `--follow` flag to `ed-telemetry events` dispatching into the live event stream.
- Added `-f` / `--follow` flag to `ed-telemetry logs` implementing zero-dependency rotating disk log tailing (`_tail_disk_logs`) with level filtering and JSON support (ADR 0028, SDD-026).
- Documented canonical CLI commands and flag behaviors across Diátaxis operational manual (`docs/how-to/run_cli_daemon.md`) and technical reference (`docs/reference/cli_interface.md`).


## [0.5.0] - 2026-10-25

### Added
- Zero-dependency CLI daemon probing (`_probe_daemon`) detecting online background daemon via `/api/v1/health`.
- Informative 12-factor daemon startup banner on `ed-telemetry serve` displaying bound network interfaces, discovered journal folder, resolution source strategy, active journal file, and API base URL (ADR 0027, SDD-025).
- Fast-fail startup validation exiting with code 1 and actionable diagnostic remediation when path discovery fails (ADR 0027, SDD-025).
- New CLI flag options `--journal-dir`, `--db-path`, and `--poll-interval` on `serve` with complete environment variable precedence (`ED_JOURNAL_DIR`, `ED_DB_PATH`, `ED_POLL_INTERVAL`, `ED_HTTP_HOST`, `ED_HTTP_PORT`, `ED_LOG_LEVEL`, `ED_LOG_FILE`).
- Diátaxis operator documentation updates in `docs/how-to/run_cli_daemon.md` and `docs/reference/cli_interface.md`.

### Fixed
- Anchored default SQLite persistent storage to canonical OS data paths (`resolve_default_db_path()`), utilizing `%LOCALAPPDATA%\ed-telemetry\telemetry.db` on Windows and `${XDG_DATA_HOME:-~/.local/share}/ed-telemetry/telemetry.db` on Linux, eliminating cwd littering and database fragmentation (#69).
- Resolved `FileSystemWatcher.journal_dir` lazy path discovery when uninitialized, and enabled `GetWatcherStatusUseCase` to dynamically extract the chronologically active journal filename (#68).
- Implemented hybrid offline disk fallback in `ed-telemetry logs` to read rotating log entries from `resolve_default_log_path()` on disk when daemon is offline (#70).
- Implemented hybrid offline streaming fallback in `ed-telemetry tail` to initiate a standalone `FileSystemWatcher` streaming lifecycle when background daemon is offline (#67).
- Preserved strict hexagonal import linter boundary contracts by isolating cross-platform path resolution in `ed_telemetry.adapters.paths`.


## [0.4.0] - 2026-10-25

### Added
- Zero-dependency HTTP REST and SSE API server (`src/ed_telemetry/adapters/driving/api/server.py`) serving live telemetry streams, snapshot sync, and RFC 7807 problem details error bubbling (ADR 0020, ADR 0024, SDD-018, SDD-022).
- Zero-framework CLI driving adapter (`src/ed_telemetry/adapters/driving/cli/main.py`) providing `serve`, `status`, `events`, `logs`, and `tail` subcommands (ADR 0024, SDD-022).
- Thread-safe SQLite persistence adapter in WAL mode (`src/ed_telemetry/adapters/driven/persistence/sqlite_adapter.py`) implementing fan-out disk storage and historical queries (ADR 0020, SDD-018).
- Real-time diagnostic log ring buffer (`src/ed_telemetry/adapters/driven/logging/buffer.py`) and endpoint `GET /api/v1/diagnostics/logs` for remote telemetry health monitoring (ADR 0025, SDD-023).
- Operational and error event bubbling (`WatcherAuditEventDTO`) into live SSE stream under topic `telemetry.audit` (ADR 0025, SDD-023).
- Cross-platform rotating log path resolution with 5 MB $\times$ 3 rotation across Windows and Linux (ADR 0025, SDD-023).
- Comprehensive test doubles (`tests/doubles/fake_adapters.py`) and Wine Windows NT integration test suite (`scripts/run_wine_tests.sh`).

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
