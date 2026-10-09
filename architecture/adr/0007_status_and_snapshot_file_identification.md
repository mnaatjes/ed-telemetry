---
title: "ADR 0007: Status and Auxiliary Snapshot File Identification and Casing Normalization"
status: "accepted"
date: "2026-10-08"
tags: ["architecture", "adr", "watcher", "snapshots", "status", "identification", "casing", "madr"]
---

# ADR 0007: Status and Auxiliary Snapshot File Identification and Casing Normalization

## 1. Context and Problem Statement

While journal log files follow dynamic timestamp-based rollover naming patterns ([ADR 0006](0006_active_journal_candidate_selection_and_sorting.md)), Frontier Developments (FDev) also outputs discrete JSON state snapshot files into the same Saved Games directory.

These snapshot files fall into two distinct operational categories:
1. **The Active Cockpit Heartbeat (`Status.json`)**: Emitted autonomously at ~1.0 Hz and immediately on cockpit toggle states.
2. **Auxiliary State Snapshots**: Discrete files created or rewritten when specific in-game menus or actions occur (`Market.json`, `Outfitting.json`, `Shipyard.json`, `ModulesInfo.json`, `Cargo.json`, `Backpack.json`, `NavRoute.json`, `FCMaterials.json`).

These snapshot files present identification challenges:
* **Filesystem Case Sensitivity Discrepancies**: Windows NTFS is case-preserving but case-insensitive. Linux filesystems (Ext4, Btrfs, ZFS) used under Proton/Wine or native development are strictly case-sensitive. While official FDev clients write canonical PascalCase (`Status.json`, `Market.json`), custom Wine prefix configurations, test simulators, or symlinks may introduce lowercase or mixed-case filenames.
* **Presence Variance**: Auxiliary snapshots do not exist when a player has not yet opened a corresponding station service (e.g. `Outfitting.json` is missing until Outfitting is visited). Candidate lookup must not treat the absence of unvisited service snapshots as an error.
* **Unnecessary I/O Chatter**: Blindly polling all auxiliary snapshot files on every clock tick wastes disk I/O and CPU cycles.
* **Unidirectional Telemetry Egress Contract**: In Frontier's architecture, snapshot files are strictly **write-only egress telemetry dumps** produced by the game engine. The game client never watches or reads these files back from disk. Modifying or replacing these files (such as injecting custom routes into `NavRoute.json`) will not alter in-game state or navigation, as the game engine overwrites them from internal memory on subsequent state updates. `ed_watcher` operates strictly as a read-only telemetry consumer.

We require an architectural decision governing how `ed_watcher` identifies, registers, normalizes, and schedules candidate lookups for status and auxiliary snapshot files.

---

## 2. Decision Drivers

* **Exhaustive Canonical Registry:** Explicitly define the complete set of supported FDev snapshot files without unbounded glob matching.
* **Cross-Platform Casing Immunity:** Identification must resolve target files regardless of filesystem case sensitivity (e.g., matching `status.json` on Linux if `Status.json` is missing).
* **Two-Tier Ingestion Decoupling:** Distinguish the continuous heartbeat polling of `Status.json` from the reactive, event-gated identification of auxiliary snapshots.
* **Graceful Absence Tolerance:** Absence of un-instantiated auxiliary files must be treated as normal inactive state, not an engine fault.

---

## 3. Considered Options

* **Option 1: Dynamic Directory Globbing (`*.json`) [REJECTED]**
  - Matching any `.json` file in the journal folder risks ingesting third-party plugin cache files, temporary files, or unrelated game logs.
* **Option 2: Strict Hardcoded Case-Sensitive Path Binding (`path / "Status.json"`) [REJECTED]**
  - Simple, but fails on Linux/Wine if test fixtures, Wine translation layers, or lowercase symlinks are used.
* **Option 3: Canonical Membership Registry with Case-Insensitive Normalization and Ingestion Decoupling (Recommended)**
  - Establish a frozen membership registry of canonical PascalCase names.
  - Implement case-insensitive directory lookup normalization for Linux/POSIX compatibility.
  - Formally separate `Status.json` (continuous cadence) from auxiliary snapshots (event-gated cadence).

---

## 4. Decision Outcome

Chosen Option: **Option 3: Canonical Membership Registry with Case-Insensitive Normalization and Ingestion Decoupling.**

### Architectural Specification

1. **Path Injection Contract**:
   Snapshot identification does not discover paths autonomously. It strictly receives `resolved_journal_dir: Path` injected directly from `PathDiscoverer.discover_journal_directory().resolved_path`:
   ```python
   class SnapshotIdentifier:
       def __init__(self, journal_dir: Path) -> None:
           self._journal_dir = journal_dir
   ```
2. **Canonical Snapshot Registry & Dynamic Extension Fallback**:
   - *Empirical Research Prerequisite*: The baseline registry represents all 9 verified FDev telemetry files (`Status.json` + 8 auxiliary files) established in `architecture/research/journal_and_snapshot_filename_spec.md`. Any addition to the core registry must be preceded by empirical research.
   - *Dynamic Extension Fallback*: To prevent system brittleness against future game expansions or third-party simulators, the registry supports dynamic runtime registration:
   ```python
   CANONICAL_STATUS_FILE = "Status.json"

   CANONICAL_AUXILIARY_SNAPSHOTS = frozenset(
       {
           "Market.json",
           "Outfitting.json",
           "Shipyard.json",
           "ModulesInfo.json",
           "Cargo.json",
           "Backpack.json",
           "NavRoute.json",
           "FCMaterials.json",
       }
   )


   class SnapshotRegistry:
       def __init__(self, custom_snapshots: set[str] | None = None) -> None:
           self._auxiliary_snapshots = set(CANONICAL_AUXILIARY_SNAPSHOTS)
           if custom_snapshots:
               self._auxiliary_snapshots.update(custom_snapshots)
   ```
3. **Execution Flow: Case-Preserving and Case-Insensitive Normalization**:
   To address cross-platform filesystem differences where Linux is case-sensitive but Windows NTFS or Wine symlinks may present lowercase:
   - *Step 1 (Fast Path)*: Check if canonical PascalCase file exists (`(self._journal_dir / name).exists()`).
   - *Step 2 (Normalization Fallback)*: If not found and running on Linux/POSIX, scan directory entries matching `entry.name.lower() == name.lower()`. If found, bind to that existing path.
   - *Step 3 (Absence)*: If no match exists, return `None` (graceful absence without error).
4. **Three-Tier Identification & Ingestion Gating Model**:
   - **`Status.json`**: Identified unconditionally as a continuous liveness target (~1.0 Hz).
   - **Auxiliary Snapshots**:
     - **Tier 1 (Inbound Target Hint Port - Fastest / Event-Driven)**: When an external consumer (e.g. downstream domain parser) observes a relevant game event, it submits an agnostic `WatcherIngestCommand(action=HINT_SNAPSHOT, target_name="Market.json")` into the watcher's `WatcherIngestReceiver` port ([ADR 0008](0008_file_ingestion_io_freshness_and_concurrency.md)). This instantly wakes the reactor to execute a debounced target lookup without requiring the watcher itself to parse JSON bytes.
     - **Tier 2 (Filesystem Event - Near-Real-Time)**: OS `watchdog` notification on `on_created` / `on_modified` for any file matching the registry triggers lookup.
     - **Tier 3 (Polling Fallback - Reliability)**: Periodic 0.5s–1.0s timeout tick scans registry to detect unannounced file writes or dropped OS notifications.

### 4.2 Error Conditions, Failure Paths, and Exception Hierarchy

1. **Target Directory Inaccessibility**:
   - *Scenario*: The injected `journal_dir` path does not exist, is unmounted, or raises OS `PermissionError` (`EACCES`/`ENOENT`) during snapshot lookup.
   - *Behavior*: Raises `SnapshotDirectoryAccessError(target_path, reason)` deriving from `WatcherError`. This is an unrecoverable configuration failure that halts the watcher startup.
2. **Unregistered Snapshot Lookup Attempt**:
   - *Scenario*: A caller or domain event requests resolution for an unknown filename not present in the canonical or custom registry (e.g. `ArbitraryFile.json`).
   - *Behavior*: Raises `UnregisteredSnapshotError(requested_name, available_registry)` or quenches lookup, preventing arbitrary path traversal outside the approved registry boundary.
3. **Casing Collision Ambiguity (Linux/POSIX Multi-Match)**:
   - *Scenario*: On Linux, multiple files differing only in case exist simultaneously (e.g. both `Status.json` AND `status.json`).
   - *Behavior*: The resolver enforces strict **Canonical PascalCase Priority**. If canonical `Status.json` exists, it is selected and a diagnostic `WatcherAuditEvent(CASING_COLLISION_DETECTED)` is emitted. If only non-canonical variants exist and multiple match, `SnapshotCollisionError` is raised.
4. **Invalid File Type (Directory / FIFO Collision)**:
   - *Scenario*: An entity matching a snapshot name exists but is a directory or special file instead of a regular file (`not path.is_file()`).
   - *Behavior*: Raises `InvalidSnapshotFileTypeError(target_path, actual_type)` and omits the target from the candidate set.
5. **Broken Symbolic Link**:
   - *Scenario*: A symlink pointing to an external mount or Wine drive is dangling (`path.is_symlink() and not path.exists()`).
   - *Behavior*: Non-fatal; logs diagnostic audit record and yields `None` without raising an exception.

#### Exception Hierarchy (`packages/ed_watcher/discovery/exceptions.py` or `packages/ed_watcher/exceptions.py`)

```text
WatcherError (Exception)
└── SnapshotIdentificationError
    ├── SnapshotDirectoryAccessError
    │   ├── target_path: Path
    │   └── reason: str ("does_not_exist" | "permission_denied" | "not_a_directory")
    ├── UnregisteredSnapshotError
    │   ├── requested_name: str
    │   └── available_registry: frozenset[str]
    ├── SnapshotCollisionError
    │   ├── canonical_name: str
    │   └── colliding_paths: tuple[Path, ...]
    └── InvalidSnapshotFileTypeError
        ├── target_path: Path
        └── actual_type: str ("directory" | "fifo" | "socket")
```

---

## 5. Consequences

### Positive
* **Zero Third-Party Collisions**: Confining lookups strictly to the frozen registry prevents accidental ingestion of non-FDev JSON files.
* **Linux / Proton Resilient**: Dynamic casing normalization ensures tests, symlinks, and Wine prefix variations resolve accurately across filesystems.
* **Minimal Disk I/O**: Eliminates wasteful polling of inactive auxiliary files by tying candidate inspection directly to journal event triggers.

### Negative
* Case-insensitive fallback scan incurs a single directory listing on POSIX if a file is present under non-canonical casing.
