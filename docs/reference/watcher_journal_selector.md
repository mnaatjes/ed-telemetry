---
title: "Reference: ed_watcher Journal Candidate Selector API"
tags: ["reference", "watcher", "journal", "candidate-selection", "api"]
created_at: "2026-10-08"
last_updated_at: "2026-10-08"
---

# Reference: ed_watcher Journal Candidate Selector API

This reference describes the classes, models, enumerations, and exceptions provided by the `ed_watcher.selector` subsystem for discovering, sorting, and selecting active and successor Elite Dangerous journal files.

Governed by [ADR 0006](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0006_active_journal_candidate_selection_and_sorting.md) and [SDD-004](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/designs/0004_active_journal_candidate_selection_and_sorting.md).

---

## 1. Primary Class: `JournalSelector`

```python
class JournalSelector:
    def __init__(self, journal_dir: Path) -> None: ...
```

The stateless evaluator responsible for discovering, filtering, sorting, and ranking journal candidates within a target directory.

### Constructor Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `journal_dir` | `Path` | *Required* | Path to the directory containing Elite Dangerous telemetry files. |

---

## 2. Methods

### `find_candidates()`

```python
def find_candidates(self) -> Sequence[JournalCandidate]: ...
```

Scans the target directory, matches files against `JOURNAL_FILE_REGEX`, and returns all valid candidates sorted in strictly ascending chronological order based on composite key `(timestamp, part, mtime)`.

#### Returns
* **`Sequence[JournalCandidate]`**: Tuple of evaluated journal candidates ordered oldest to newest.

#### Raises
* **`JournalDirectoryAccessError`**: If the target directory does not exist, is not a directory, or has insufficient read permissions.

---

### `get_active_journal()`

```python
def get_active_journal(self) -> JournalCandidate | None: ...
```

Resolves the current active journal file (the highest-ranking candidate in the directory).

#### Returns
* **`JournalCandidate | None`**: The candidate representing the newest journal file, or `None` if the directory contains zero matching journal files (non-fatal waiting condition).

#### Raises
* **`JournalDirectoryAccessError`**: If directory access fails.

---

### `get_successor()`

```python
def get_successor(self, current: JournalCandidate) -> JournalCandidate | None: ...
```

Evaluates whether a strictly newer journal candidate exists in the directory relative to `current`. Used by the live daemon reactor during runtime idle checks and filesystem notifications to detect session transitions or multi-part rollovers (`.01.log` $\to$ `.02.log`).

#### Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `current` | `JournalCandidate` | *Required* | The candidate currently being tailed or tracked. |

#### Returns
* **`JournalCandidate | None`**: The newer candidate if one ranks higher than `current`, otherwise `None`.

---

### `evaluate_candidate()`

```python
def evaluate_candidate(self, filepath: Path) -> JournalCandidate: ...
```

Evaluates an individual file into a `JournalCandidate`. Automatically extracts build flavor, UTC timestamp, and part number. Gracefully degrades to `(datetime.min, 0, mtime)` if filename parsing fails.

---

## 3. Data Models & Value Objects

### `JournalCandidate`

```python
@dataclass(frozen=True)
class JournalCandidate:
    path: Path
    filename: str
    build: str | None
    timestamp: datetime
    part: int
    mtime: float
    is_standard_format: bool
```

An immutable, comparable value object representing an evaluated journal file. Supports Python comparison operators (`<`, `<=`, `>`, `>=`) evaluated against the composite sort key: `(timestamp, part, mtime)`.

#### Properties & Attributes

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `path` | `Path` | Absolute filesystem path. |
| `filename` | `str` | Base filename (e.g. `Journal.2026-10-08T120000.01.log`). |
| `build` | `str \| None` | Build identifier (`"Alpha"`, `"Beta"`), or `None` for production. |
| `timestamp` | `datetime` | UTC timestamp parsed from filename (`datetime.min` if non-standard). |
| `part` | `int` | Integer part number (`1`, `2`, or `0` if non-standard). |
| `mtime` | `float` | Filesystem modification timestamp (`st_mtime`). |
| `is_standard_format` | `bool` | `True` if filename adhered to canonical FDev format; `False` if non-standard fallback was used. |

---

## 4. Enumerations

### `StreamPosition`

```python
class StreamPosition(StrEnum):
    HEAD = "head"
    TAIL = "tail"
    LOCATE_EVENT = "locate_event"
```

Declarative startup stream positioning mode:
* **`HEAD` (`"head"`)**: Begins tailing from byte offset 0 (full historical replay).
* **`TAIL` (`"tail"`)**: Seeks directly to current end-of-file (live monitoring only).
* **`LOCATE_EVENT` (`"locate_event"`)**: Reverse-scans backwards from EOF to locate state event anchors.

---

## 5. Exceptions

### Hierarchy

```text
WatcherError
└── JournalDirectoryAccessError
```

### `JournalDirectoryAccessError`

Raised when `JournalSelector` cannot inspect the target directory.

```python
class JournalDirectoryAccessError(WatcherError):
    target_path: Path
    reason: str  # 'does_not_exist', 'not_a_directory', 'permission_denied', 'os_error'
```

---

## 6. Usage Example

```python
from pathlib import Path
from ed_watcher import (
    PathDiscoverer,
    JournalSelector,
    StreamPosition,
    JournalDirectoryAccessError,
)

# 1. Discover the directory
discoverer = PathDiscoverer()
result = discoverer.discover_journal_directory()

# 2. Select the active journal
selector = JournalSelector(result.path)
active = selector.get_active_journal()

if active is None:
    print("No journal files found yet. Waiting for game startup...")
else:
    print(f"Active Journal: {active.filename}")
    print(f"Part Number:    {active.part}")
    print(f"Game Timestamp: {active.timestamp.isoformat()}")

    # 3. Check for successor during runtime
    successor = selector.get_successor(active)
    if successor:
        print(f"Rollover detected! Switching to: {successor.filename}")
```
