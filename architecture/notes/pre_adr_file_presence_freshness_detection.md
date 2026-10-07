---
title: "Pre-ADR Architectural Considerations: File Discovery, Presence & Freshness Detection"
tags: ["architecture", "watcher", "ingestion", "file-detection", "freshness", "pre-adr"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# Pre-ADR Architectural Considerations: File Discovery, Presence & Freshness Detection

## 1. Scope Boundary & Phase Naming

### Proposed Scoped Phase Name: **File Presence & Freshness Detection (FPFD)**
This phase is strictly confined to:
1. Determining if a candidate target file physically exists.
2. Confirming the file contains readable, non-empty content (`st_size > 0`).
3. Determining if that content has not yet been processed (unseen bytes or modified payload).

It intentionally excludes:
- Downstream JSON decoding.
- Domain schema validation.
- Business event dispatch.

---

## 2. Consideration 1: Divergent OS Flows vs. Unified Abstraction

### Diagnostic
- **Windows (NTFS)**:
  - File locking requires explicit shared-read permissions (`FILE_SHARE_READ`) to avoid collision with the game client (`PermissionError: [WinError 32]`).
  - Kernel notifications via `ReadDirectoryChangesW` are efficient but batch-coalesced.
- **Linux (Ext4/Btrfs via Proton / Wine / Native)**:
  - POSIX file descriptors can be read concurrently without mandatory file locks.
  - Kernel notifications via `inotify` are reliable locally, but **diverge** when the journal directory resides on Wine-simulated drives (`dosdevices`), container bind-mounts, or network mounts where kernel events fail to propagate.

### Architectural Resolution
- **Unified Outer Abstraction, Divergent Driver Strategy (Adapter Pattern)**:
  The `WatcherPort` contract remains $100\%$ unified across platforms:
  ```
  PathDiscoverer -> FilePresenceDetector -> FreshnessChecker -> Stream/ReadAdapter
  ```
- **Where Divergence is Confined**:
  - **Path Discovery**: Already decoupled via `WindowsPathStrategy` vs. `LinuxProtonPathStrategy` (governed by ADR 0004 & SDD-003).
  - **File Descriptor Opening**: On Windows, file opening is wrapped with non-exclusive sharing semantics (`open(..., 'rb')` standard in Python is non-exclusive, but binary share flags are verified). On Linux, standard POSIX open is used.
  - **Event Trigger vs. Poll**: Rather than creating two branching execution paths across the codebase, both environments run the **unified hybrid event loop**: wait for OS notification with a bounded timeout fallback (1.0s). On Linux/Wine where notifications might drop, the timeout acts as the continuous driver; on Windows, OS events accelerate execution.

---

## 3. Consideration 2: Execution Order of File Ingestion

### Does it vary by OS?
- **No.** The logical execution order must be identical across operating systems to ensure deterministic domain state regardless of whether the user runs native Windows or Linux/Proton.

### How does it vary by file type (Journal vs. Snapshot)?
The ingestion order follows a strict two-stage lifecycle:

```
[Phase 1: Boot & Historical Catch-Up]
   │
   ├─ Step 1.1: Identify Newest Active Journal via `max(..., key=os.path.getctime)`
   ├─ Step 1.2: Replay Journal Stream (Offset 0 -> EOF) to establish active SessionContext (Cmdr, FID, System)
   └─ Step 1.3: Reconcile Baseline Snapshot State:
                 Read `Status.json` -> verify `timestamp >= session_start`
                 (Optional) Read `Cargo.json`, `ModulesInfo.json`, `NavRoute.json`
   │
[Phase 2: Steady-State Runtime (Continuous Loop)]
   │
   ├─ Priority A: Steady-State Journal Stream Ingestion (High Frequency Append-Tailing)
   ├─ Priority B: Fast Polling / Change Detection of `Status.json` (~1 Hz HUD/Cockpit Sync)
   └─ Priority C: Reactive Snapshot Ingestion (`Market.json`, `Cargo.json`) triggered by Journal Events
```

#### Rationale for Order:
1. **Journal Precedes Snapshots on Boot**: You cannot validate whether `Status.json` or `Cargo.json` belongs to the current play session without first reading the `Fileheader` / `Commander` / `LoadGame` event in the active journal to acquire the session start time and Commander ID.
2. **Snapshots are Subordinate to Journal Events**: Files like `Market.json` and `Shipyard.json` must only be examined when the active journal explicitly logs a `Market` or `Shipyard` event, avoiding redundant disk reads.

---

## 4. Consideration 3: Ingestion Strategy: Full Read vs. Delta Monitoring

### Strategy Matrix by File Type

| Target File | Ingestion Strategy | Freshness Metric | Rationale |
| :--- | :--- | :--- | :--- |
| **Journal Files (`Journal.*.log`)** | **Delta Stream (Offset Checkpointing)** | `current_size > last_processed_offset` | Append-only files grow up to hundreds of megabytes. Re-reading whole files on every write is an $O(N)$ CPU/disk performance anti-pattern. Only new byte slices are read. |
| **Status Snapshot (`Status.json`)** | **Delta Ingestion via Content Hashing** | `stat().st_mtime` change AND `hash(raw_bytes) != last_hash` | Small file (~1-2 KB), rewritten every ~1s. Always read in whole, but only dispatched downstream if content hash changes. |
| **Event Snapshots (`Market.json`, etc.)** | **One-Shot Whole Read on Trigger** | Triggered by Journal Event AND `file.exists()` | Read completely upon receipt of triggering journal event, processed once, then held in cache until the next event. |

---

## 5. Consideration 4: Adoption of `max(..., key=os.path.getctime)` and Execution Order

The user-mandated baseline `max(journal_files, key=os.path.getctime)` is adopted for initial active journal selection.

### Deterministic Execution Order for Active Journal Selection:
1. **Directory Validation**: Verify target directory exists and is accessible.
2. **File Enumeration & Regex Filtering**:
   Scan directory entries and filter strictly using `JOURNAL_FILE_REGEX` (discarding temporary files, non-journal files, and subdirectories).
3. **Empty Set Check**:
   If candidate set is empty, transition to `WAITING_FOR_JOURNAL` state and sleep until created.
4. **Primary Selection (`getctime`)**:
   Compute `target_file = max(matching_files, key=os.path.getctime)`.
5. **Freshness & Rollover Tiebreaking**:
   If multiple files share identical creation timestamps or rollover occurs, tiebreak using the part number extracted from the regex (`part = int(match.group('part'))`).
6. **Descriptor Binding**:
   Open persistent handle to `target_file` in binary mode and initialize `last_processed_offset = 0` (or `last_processed_offset = EOF` depending on replay policy).

---

## 6. Consideration 5: Stream vs. Read Decision: Impact on Flow & Fallback Strategies

The architectural decision to **Stream** Journals and **Read in Whole** Snapshots directly influences execution flow, error recovery, and fallback logic:

### Flow Impact
- **Journal Streaming Flow**:
  - The file descriptor remains open across turns.
  - The thread/task performs non-blocking reads (`readline()` or raw byte slice) up to `EOF`.
  - When `EOF` is reached, the handle is **not closed**; the engine simply records `last_offset = handle.tell()` and awaits the next trigger or poll tick.
- **Snapshot Whole-Read Flow**:
  - Transient open-read-close pattern.
  - Ephemeral file handles avoid locking disputes with FDev write routines.

### Fallback & Failure Strategies

1. **Truncation Race on Snapshots (Read in Whole)**:
   - *Impact*: Calling `read_bytes()` during an FDev write cycle returns `0` bytes or truncated JSON.
   - *Fallback*: Do **not** advance freshness state. Retain previous valid snapshot. Schedule immediate backoff retry (20ms, 40ms, 80ms).
2. **Incomplete Line Flush on Journal (Streaming)**:
   - *Impact*: The game client writes a line but has only flushed half of the bytes when the watcher reads up to `EOF`.
   - *Fallback*: Check if the read buffer ends in a newline (`\n`). If it does not end in `\n`, seek back to `last_offset` and wait for the remaining bytes to flush.
3. **Journal Part Rotation Rollover**:
   - *Impact*: Game client closes `01.log` and opens `02.log`. The streaming handle on `01.log` will permanently read `EOF`.
   - *Fallback*: When `EOF` is reached on `01.log`, perform a quick directory presence check for `02.log` or a newer `ctime` file. If a newer journal is found, drain `01.log` to completion, close the descriptor, and rebind the stream to `02.log`.

---

## 7. Tooling & Technology Identification

| Tool / Library | Classification | Role in FPFD Phase | Rationale |
| :--- | :--- | :--- | :--- |
| **`pathlib.Path`** | Existing (Stdlib) | Filesystem path normalization & existence checking | Cross-platform path abstraction (Windows backslashes vs. POSIX slashes). |
| **`os.path.getctime`** | Existing (Stdlib) | Newest journal candidate selection | Mandated baseline for selecting active journal file. |
| **`re`** | Existing (Stdlib) | Filename regex parsing (`JOURNAL_FILE_REGEX`) | Extracts timestamp, build prefix, and part number. |
| **`hashlib` (BLAKE2b)** | Existing (Stdlib) | Fast snapshot content hashing | $O(1)$ change detection for `Status.json` raw bytes without JSON parsing overhead. |
| **`watchdog`** | **New (Dependency)** | Cross-platform filesystem event monitoring (`on_created`, `on_modified`) | Native OS notification drivers (`inotify` on Linux, `ReadDirectoryChangesW` on Windows). |
| **`asyncio` / `threading`** | Existing (Stdlib) | Event loop and periodic fallback ticker | Coordinates hybrid event trigger + 1.0s timeout polling loop. |
| **`ctypes` / Win32 API** | Existing (Internal) | Windows folder path discovery & share verification | Used by `WindowsPathStrategy` for KnownFolders and non-blocking file access. |
