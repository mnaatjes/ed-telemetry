---
title: "ADR 0018: Expanded Telemetry Use Cases and On-Demand Query Capabilities"
status: "accepted"
date: "2026-10-25"
tags: ["architecture", "adr", "use-cases", "query-capabilities", "watcher", "hexagonal"]
---

# ADR 0018: Expanded Telemetry Use Cases and On-Demand Query Capabilities

## 1. Context and Problem Statement

Following the completion of [ADR 0017](0017_migration_to_standard_hexagonal_template_and_service_retirement.md) and [SDD-015](../designs/0015_hexagonal_topology_refactor_and_copier_migration.md), `ed-telemetry` operates strictly within a single-root hexagonal architecture (`src/ed_telemetry/`).

However, the application layer (`core/use_cases/`) currently exposes only high-level streaming management (`ProcessTelemetryStreamUseCase`), watcher health checks (`GetWatcherStatusUseCase`), and a baseline sync interactor (`SyncJournalSnapshotUseCase`). The underlying driven adapter infrastructure (`adapters/driven/watcher/`) possesses extensive, battle-tested capabilities that remain unexposed to Driving Adapters (CLI, upcoming MCP server, and REST API):
1. **OS Path Discovery:** Dynamic resolution of Elite Dangerous directories across Linux Proton prefixes and Windows NT Known Folders.
2. **Journal Catalog & Chronological Ordering:** Evaluation, sorting, and metadata extraction across all historical and active `Journal.<timestamp>.<part>.log` candidate files.
3. **Point-in-Time Status Inspection:** Safe whole-reading and normalization of `Status.json` (ship flags, pips, fuel, coordinates, firegroups).
4. **Auxiliary Snapshot Inspection:** On-demand access to game auxiliary state files (`Market.json`, `NavRoute.json`, `Cargo.json`, `Shipyard.json`, `Outfitting.json`, `Backpack.json`, `ModulesInfo.json`).
5. **Operational Ingest Hint Injection:** Programmatic submission of high-priority ingestion hints (`HINT_SNAPSHOT`, `HINT_ROLLOVER`) into the watcher reactor queue.

We must formally expand the application use case catalog to expose these capabilities through pure driving ports and immutable boundary DTOs, strictly upholding the 28 Hexagonal Truths.

---

## 2. Decision Drivers

* **Expose Infrastructure Power:** Surface existing discovery, journal selection, and snapshot reading logic to driving callers without requiring them to bypass core layers.
* **Support Multi-Interface Driving Adapters:** Provide discrete, specialized query use cases tailored for CLI commands (`ed-telemetry path`, `ed-telemetry journals`, `ed-telemetry status --game`, `ed-telemetry snapshot <target>`) and MCP server tools (`get_current_ship_status`, `get_navigation_route`, `get_market_data`).
* **Preserve Hexagonal Boundary Purity:**
  - Zero framework dependencies in `core/` (`HEXA-TRUTH-13`).
  - Immutable frozen DTOs co-located within `core/ports/` (`HEXA-TRUTH-04, 28`).
  - Strict naming invariants (`^[A-Z][a-zA-Z0-9]+UseCase$` with approved verb prefixes) (`HEXA-TRUTH-11`).
  - Test double parity for all driven port extensions (`HEXA-TRUTH-27`).

---

## 3. Decision Outcome

Chosen Option: **Establish 5 new Use Cases, their associated Driving Ports, boundary DTOs, and Driven Port extensions on `WatcherPort`:**

1. **`DiscoverJournalPathUseCase` (`DiscoverJournalPathPort`)**: Resolves the local Elite Dangerous journal directory path and discovery method.
2. **`ListJournalFilesUseCase` (`ListJournalFilesPort`)**: Scans and returns all historical and active journal files in chronological sequence with metadata.
3. **`GetLatestGameStatusUseCase` (`GetLatestGameStatusPort`)**: Inspects and extracts the freshest `Status.json` raw payload and status metadata.
4. **`InspectAuxiliarySnapshotUseCase` (`InspectAuxiliarySnapshotPort`)**: Retrieves the latest known payload for a specified auxiliary state file (e.g. `Market.json`, `NavRoute.json`).
5. **`TriggerSnapshotRefreshUseCase` (`TriggerSnapshotRefreshPort`)**: Injects an operational snapshot refresh hint into the active watcher reactor.

---

## 4. Architectural Port & DTO Specifications

### 4.1 Boundary Data Transfer Objects (`core/ports/dto/telemetry_dto.py`)

| DTO Class | Boundary Direction | Description & Fields |
| :--- | :--- | :--- |
| `JournalPathDTO` | Driving Port Return | `resolved_path: str`, `platform: str`, `discovery_source: str` |
| `JournalCandidateDTO` | Value Object / Element | `filename: str`, `path: str`, `timestamp: datetime`, `part: int`, `mtime: float`, `is_standard_format: bool` |
| `JournalFileListDTO` | Driving Port Return | `journal_dir: str`, `candidates: tuple[JournalCandidateDTO, ...]`, `active_journal: str \| None` |
| `GameStatusSnapshotDTO` | Driving Port Return | `exists: bool`, `target_path: str \| None`, `timestamp: datetime \| None`, `raw_payload: bytes`, `raw_hash: str \| None` |
| `AuxiliarySnapshotDTO` | Driving Port Return | `target_name: str`, `exists: bool`, `target_path: str \| None`, `timestamp: datetime \| None`, `raw_payload: bytes`, `raw_hash: str \| None` |
| `HintSubmissionDTO` | Driving Port Return | `action: str`, `target_name: str \| None`, `accepted: bool`, `detail: str` |

### 4.2 Driving Ports (`core/ports/driving/telemetry_port.py`)

```python
@runtime_checkable
class DiscoverJournalPathPort(DrivingPort, Protocol):
    def discover_path(self, override_path: str | None = None) -> JournalPathDTO: ...


@runtime_checkable
class ListJournalFilesPort(DrivingPort, Protocol):
    def list_journals(self) -> JournalFileListDTO: ...


@runtime_checkable
class GetLatestGameStatusPort(DrivingPort, Protocol):
    def get_game_status(self) -> GameStatusSnapshotDTO: ...


@runtime_checkable
class InspectAuxiliarySnapshotPort(DrivingPort, Protocol):
    def inspect_snapshot(self, snapshot_name: str) -> AuxiliarySnapshotDTO: ...


@runtime_checkable
class TriggerSnapshotRefreshPort(DrivingPort, Protocol):
    def refresh_snapshot(self, snapshot_name: str) -> HintSubmissionDTO: ...
```

### 4.3 Driven Port Extensions (`core/ports/driven/telemetry_driven_port.py`)

`WatcherPort` is updated to expose synchronous query and hint dispatch operations:
```python
@runtime_checkable
class WatcherPort(LifecyclePort, StreamSourcePort, DrivenPort, Protocol):
    @property
    def journal_dir(self) -> str | None: ...
    def discover_path(self, override_path: str | None = None) -> JournalPathDTO: ...
    def list_journals(self) -> JournalFileListDTO: ...
    def read_status_snapshot(self) -> GameStatusSnapshotDTO: ...
    def read_auxiliary_snapshot(self, name: str) -> AuxiliarySnapshotDTO: ...
    def submit_ingest_hint(self, action: str, target_name: str | None = None) -> HintSubmissionDTO: ...
```

---

## 5. Consequences

### Positive
* **Rich Application Layer:** Driving callers have fine-grained on-demand query access to journal files, live game status, and auxiliary market/route data.
* **MCP Readiness:** Provides 1-to-1 mapping for MCP AI agent tool calls (`find_game_path`, `list_journals`, `get_ship_status`, `get_market_snapshot`, `refresh_snapshot`).
* **Preserved Boundary Isolation:** The use cases depend strictly on `WatcherPort`, ensuring that filesystem operations, Windows NT Win32 APIs, and Wine/Proton logic remain strictly encapsulated within `adapters/driven/watcher/`.

### Negative / Trade-Offs
* `FakeWatcherAdapter` must implement the 5 query/hint methods to preserve full test double parity (`HEXA-TRUTH-27`).
