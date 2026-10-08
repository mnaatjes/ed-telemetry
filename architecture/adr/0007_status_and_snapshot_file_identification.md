---
title: "ADR 0007: Status and Auxiliary Snapshot File Identification and Casing Normalization"
status: "proposed"
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

1. **Canonical Snapshot Registry**:
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
   ```
2. **Case-Insensitive Resolution**:
   When resolving a snapshot file within the target journal directory:
   - Check direct canonical path: `(journal_dir / canonical_name).exists()`.
   - If missing on Linux/POSIX, scan the directory for a case-insensitive match (`name.lower() == canonical_name.lower()`) to normalize casing dynamically.
3. **Identification & Gating Strategy**:
   - **`Status.json` Candidate**: Identified unconditionally upon watcher initialization as a permanent liveness target.
   - **Auxiliary Snapshot Candidates**: Identified reactively. The watcher inspects an auxiliary snapshot only when:
     1. The active journal stream emits a triggering event (e.g. `Market`, `Cargo`, `NavRoute`), OR
     2. An explicit baseline catch-up check is requested upon startup.
   - If the candidate file does not physically exist on disk, lookup yields empty without raising an error.

---

## 5. Consequences

### Positive
* **Zero Third-Party Collisions**: Confining lookups strictly to the frozen registry prevents accidental ingestion of non-FDev JSON files.
* **Linux / Proton Resilient**: Dynamic casing normalization ensures tests, symlinks, and Wine prefix variations resolve accurately across filesystems.
* **Minimal Disk I/O**: Eliminates wasteful polling of inactive auxiliary files by tying candidate inspection directly to journal event triggers.

### Negative
* Case-insensitive fallback scan incurs a single directory listing on POSIX if a file is present under non-canonical casing.
