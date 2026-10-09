---
title: "Reference: ed_watcher Status and Snapshot Identifier API"
tags: ["reference", "watcher", "snapshots", "status", "casing", "api"]
created_at: "2026-10-09"
last_updated_at: "2026-10-09"
---

# Reference: ed_watcher Status and Snapshot Identifier API

This reference describes the classes, models, catalogs, and exceptions provided by the `ed_watcher.snapshots` subsystem for identifying, resolving, and normalizing Frontier Developments state snapshots.

Governed by [ADR 0007](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0007_status_and_snapshot_file_identification.md) and [SDD-005](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/designs/0005_status_and_snapshot_file_identification.md).

---

## 1. Primary Class: `SnapshotIdentifier`

```python
class SnapshotIdentifier:
    def __init__(
        self,
        journal_dir: Path,
        registry: SnapshotRegistry | None = None,
        posix_mode: bool | None = None,
    ) -> None: ...
```

Coordinates filesystem inspection, fast-path resolution, and cross-platform casing normalization.

### Methods

#### `resolve_status()`
```python
def resolve_status(self) -> SnapshotCandidate | None: ...
```
Resolves the active cockpit heartbeat file (`Status.json`). Returns `None` if absent on disk.

#### `resolve_auxiliary(name: str)`
```python
def resolve_auxiliary(self, name: str) -> SnapshotCandidate | None: ...
```
Resolves a specific auxiliary snapshot file (e.g. `"Market.json"`, `"Cargo.json"`).
* **Raises**: `UnregisteredSnapshotError` if `name` is not recognized in `SnapshotRegistry`.
* **Returns**: `SnapshotCandidate` if found, or `None` if the file has not yet been instantiated by the game client.

#### `resolve_all_available()`
```python
def resolve_all_available(self) -> Sequence[SnapshotCandidate]: ...
```
Scans the directory and returns candidates for all currently instantiated registered snapshots. Gracefully ignores absent or quarantined invalid node types.

---

## 2. Catalog & Validation: `SnapshotRegistry`

```python
class SnapshotRegistry:
    def __init__(self, custom_snapshots: set[str] | None = None) -> None: ...
```

Governs the approved membership allowlist for FDev telemetry snapshot files.

### Canonical Constants
* **`CANONICAL_STATUS_FILE`**: `"Status.json"`
* **`CANONICAL_AUXILIARY_SNAPSHOTS`**:
  - `"Market.json"`, `"Outfitting.json"`, `"Shipyard.json"`, `"ModulesInfo.json"`
  - `"Cargo.json"`, `"Backpack.json"`, `"NavRoute.json"`, `"ShipLocker.json"`, `"FCMaterials.json"`

### Methods

#### `is_registered(filename: str) -> bool`
Case-insensitively checks if a filename belongs to the registered catalog.

#### `canonical_name(query: str) -> str | None`
Resolves a query string (e.g. `"market.json"`) to its canonical PascalCase name (`"Market.json"`).

#### `register_custom(filename: str) -> None`
Dynamically registers a custom auxiliary snapshot. Enforces three security validation gates:
1. **Pure Basename**: Rejects directory separators (`/`, `\`) and parent traversal (`..`).
2. **Extension Invariant**: Requires `.json` extension.
3. **Stream Separation**: Rejects filenames beginning with `"Journal"` to prevent collisions with journal streams.
* **Raises**: `SnapshotRegistrationError` on invariant violation.

---

## 3. Data Models

### `SnapshotCandidate`

```python
@dataclass(frozen=True)
class SnapshotCandidate:
    canonical_name: str
    resolved_path: Path
    exists: bool
    is_canonical_casing: bool
    mtime: float
    size: int
```

Immutable value object representing an identified snapshot file on disk.

---

## 4. Exceptions

```text
WatcherError
└── SnapshotIdentificationError
    ├── SnapshotDirectoryAccessError
    ├── UnregisteredSnapshotError
    ├── SnapshotCollisionError
    ├── SnapshotRegistrationError
    └── InvalidSnapshotFileTypeError
```

---

## 5. Usage Example

```python
from pathlib import Path
from ed_watcher import PathDiscoverer, SnapshotIdentifier, SnapshotRegistry

# 1. Discover the journal directory
dir_path = PathDiscoverer().discover_journal_directory().path

# 2. Initialize identifier
identifier = SnapshotIdentifier(dir_path)

# 3. Resolve heartbeat
status_candidate = identifier.resolve_status()
if status_candidate:
    print(f"Status file path: {status_candidate.resolved_path}")

# 4. Resolve auxiliary file (e.g. after station market event)
market_candidate = identifier.resolve_auxiliary("Market.json")
if market_candidate:
    print(f"Market snapshot size: {market_candidate.size} bytes")
```
