---
title: "SDD 0016: Expanded Telemetry Use Cases and On-Demand Query Capabilities"
status: "accepted"
date: "2026-10-25"
tags: ["architecture", "sdd", "use-cases", "query-capabilities", "watcher", "hexagonal"]
---

# SDD 0016: Expanded Telemetry Use Cases and On-Demand Query Capabilities

## 1. Context and Architectural Overview

This Software Design Document formalizes the structural specifications and interactor designs for the 5 expanded use cases adopted in [ADR 0018](../adr/0018_expanded_telemetry_use_cases_and_query_capabilities.md).

```
   [Driving Adapters: CLI, MCP Server, REST API]
                         │
      ┌──────────────────┼────────────────────────┬─────────────────────┐
      ▼                  ▼                        ▼                     ▼
DiscoverJournal    ListJournalFiles      GetLatestGameStatus   InspectAuxiliarySnapshot
   PathPort              Port                    Port                    Port
      │                  │                        │                     │
      ▼                  ▼                        ▼                     ▼
DiscoverJournal    ListJournalFiles      GetLatestGameStatus   InspectAuxiliarySnapshot
  PathUseCase          UseCase                 UseCase                 UseCase
      │                  │                        │                     │
      └──────────────────┼────────────────────────┴─────────────────────┘
                         ▼
             [Driven Port: WatcherPort]
                         │
                         ▼
        [Driven Adapter: FileSystemWatcher]
        ├── PathDiscoverer (Linux/Win32)
        ├── JournalSelector
        ├── SnapshotIdentifier & Registry
        └── SnapshotReader & FreshnessTracker
```

---

## 2. Port Interfaces and Boundary DTOs

### 2.1 Pure DTO Definitions (`core/ports/dto/telemetry_dto.py`)

All boundary DTOs inherit from `DataTransferObject` and are decorated with `@dataclass(frozen=True, slots=True)`:

```python
@dataclass(frozen=True, slots=True)
class JournalPathDTO(DataTransferObject):
    resolved_path: str
    platform: str
    discovery_source: str


@dataclass(frozen=True, slots=True)
class JournalCandidateDTO(DataTransferObject):
    filename: str
    path: str
    timestamp: datetime
    part: int
    mtime: float
    is_standard_format: bool


@dataclass(frozen=True, slots=True)
class JournalFileListDTO(DataTransferObject):
    journal_dir: str
    candidates: tuple[JournalCandidateDTO, ...]
    active_journal: str | None


@dataclass(frozen=True, slots=True)
class GameStatusSnapshotDTO(DataTransferObject):
    exists: bool
    target_path: str | None
    timestamp: datetime | None
    raw_payload: bytes
    raw_hash: str | None


@dataclass(frozen=True, slots=True)
class AuxiliarySnapshotDTO(DataTransferObject):
    target_name: str
    exists: bool
    target_path: str | None
    timestamp: datetime | None
    raw_payload: bytes
    raw_hash: str | None


@dataclass(frozen=True, slots=True)
class HintSubmissionDTO(DataTransferObject):
    action: str
    target_name: str | None
    accepted: bool
    detail: str
```

---

## 3. Use Case Interactors (`core/use_cases/`)

All use cases follow strict constructor dependency injection binding only abstract driven ports (`WatcherPort`), maintain zero mutable state across method invocations, and conform to `^[A-Z][a-zA-Z0-9]+UseCase$`.

### 3.1 `DiscoverJournalPathUseCase`
- **Port:** `DiscoverJournalPathPort`
- **Dependencies:** `watcher: WatcherPort`
- **Method:** `discover_path(override_path: str | None = None) -> JournalPathDTO`

### 3.2 `ListJournalFilesUseCase`
- **Port:** `ListJournalFilesPort`
- **Dependencies:** `watcher: WatcherPort`
- **Method:** `list_journals() -> JournalFileListDTO`

### 3.3 `GetLatestGameStatusUseCase`
- **Port:** `GetLatestGameStatusPort`
- **Dependencies:** `watcher: WatcherPort`
- **Method:** `get_game_status() -> GameStatusSnapshotDTO`

### 3.4 `InspectAuxiliarySnapshotUseCase`
- **Port:** `InspectAuxiliarySnapshotPort`
- **Dependencies:** `watcher: WatcherPort`
- **Method:** `inspect_snapshot(snapshot_name: str) -> AuxiliarySnapshotDTO`

### 3.5 `TriggerSnapshotRefreshUseCase`
- **Port:** `TriggerSnapshotRefreshPort`
- **Dependencies:** `watcher: WatcherPort`
- **Method:** `refresh_snapshot(snapshot_name: str) -> HintSubmissionDTO`

---

## 4. Composition Root Wiring (`bootstrap/container.py`)

The production composition root updates `Container` to instantiate and expose all 5 use cases:
```python
@dataclass(frozen=True, slots=True)
class Container:
    get_watcher_status_use_case: GetWatcherStatusUseCase
    process_telemetry_stream_use_case: ProcessTelemetryStreamUseCase
    sync_journal_snapshot_use_case: SyncJournalSnapshotUseCase
    discover_journal_path_use_case: DiscoverJournalPathUseCase
    list_journal_files_use_case: ListJournalFilesUseCase
    get_latest_game_status_use_case: GetLatestGameStatusUseCase
    inspect_auxiliary_snapshot_use_case: InspectAuxiliarySnapshotUseCase
    trigger_snapshot_refresh_use_case: TriggerSnapshotRefreshUseCase
```

---

## 5. Verification Plan

1. **AST Boundary & Import Linter Compliance:**
   - Verify `tests/architecture/test_boundaries.py` and `lint-imports` pass with all 28 Hexagonal Truths preserved.
2. **Offline Test Doubles:**
   - Update `FakeWatcherAdapter` with deterministic in-memory responses for all 5 methods.
3. **Unit Tests:**
   - Author dedicated unit tests in `tests/unit/core/test_use_cases.py` exercising each new use case against `FakeWatcherAdapter`.
   - Update `tests/unit/core/test_container.py` validating complete container dependency wiring.
