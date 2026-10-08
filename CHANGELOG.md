# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
