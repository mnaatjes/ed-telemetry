---
title: "SDD-017: Realignment of Wine Cross-Platform Simulation Testing with Standard Hexagonal Architecture"
tags: ["sdd", "wine", "testing", "hexagonal", "verification"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-017: Realignment of Wine Cross-Platform Simulation Testing with Standard Hexagonal Architecture

## 1. Executive Summary
This design document defines the structural realignment of `scripts/run_wine_tests.sh` to comply with the hexagonal codebase topology established in ADR 0017 and expanded in ADR 0018.

## 2. Test Execution Stages Under Wine

The Wine test runner executes discrete Python invocations targeting Windows Python (`python.exe`) within an isolated Wine prefix (`.cache/winepfx`):

1. **Platform & Registry Diagnostic:**
   - Validates Windows Python 3.11 runtime, `platform.system() == 'Windows'`, and `winreg` module availability.
2. **Windows Path Strategy Discovery:**
   - Imports `ed_telemetry.adapters.driven.watcher.discovery.strategies.windows.WindowsPathStrategy`.
   - Verifies candidate path discovery against simulated Windows environment and Registry keys.
3. **Journal Candidate Selector & Rollover:**
   - Imports `ed_telemetry.adapters.driven.watcher.selector.JournalSelector`.
   - Tests candidate sorting, timestamp parsing, active journal detection, and successor rollover under Windows path syntax.
4. **Status & Auxiliary Snapshot Identifier:**
   - Imports `ed_telemetry.adapters.driven.watcher.snapshots.SnapshotIdentifier`.
   - Verifies discovery of `Status.json`, `Market.json`, and auxiliary snapshots on Windows temporary filesystems.
5. **Reactive File Ingestion Engine:**
   - Imports `ed_telemetry.adapters.driven.watcher.engine.WatcherReactor`.
   - Verifies streaming journal line reading, heartbeat status ingestion, and part rollover drain on Windows.
6. **Threaded FileSystemWatcher Adapter:**
   - Imports `ed_telemetry.adapters.driven.watcher.watcher.FileSystemWatcher`.
   - Verifies threaded background watcher loop, polling dispatch, and clean shutdown on Windows NT.
7. **Hexagonal Container & Use Cases Verification:**
   - Imports `ed_telemetry.bootstrap.container.Container`.
   - Instantiates `Container(journal_dir=win_dir)`.
   - Executes and asserts outputs for:
     - `FindJournalPathUseCase` -> `JournalPathDTO`
     - `GetJournalFilesUseCase` -> `JournalFileListDTO`
     - `GetLatestGameStatusUseCase` -> `GameStatusSnapshotDTO`
     - `GetAuxiliarySnapshotUseCase` -> `AuxiliarySnapshotDTO`
     - `SubmitSnapshotRefreshUseCase` -> `HintSubmissionDTO`
   - Verifies boundary DTO immutability (`FrozenInstanceError`) and dictionary conversions.

## 3. Verification Strategy
- Execute `bash scripts/run_wine_tests.sh` to verify zero regressions under Wine.
- Maintain existing fail-fast assertions (`set -euo pipefail`).
