---
title: "Pre-ADR Architectural Considerations: File Discovery, Presence & Freshness Detection"
tags: ["architecture", "watcher", "ingestion", "file-detection", "freshness", "pre-adr"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# Pre-ADR Architectural Considerations: File Discovery, Presence & Freshness Detection

## 1. Scope Boundary & Phase Naming

### Scoped Phase Name: **File Presence & Freshness Detection (FPFD)**
This architectural phase is strictly confined to:
1. Determining if a candidate target file physically exists.
2. Confirming the file contains readable, non-empty content (`st_size > 0`).
3. Determining if that content has not yet been processed (unseen byte offsets or modified payload checksum).

**Excluded from this phase:**
- Downstream JSON decoding.
- Domain schema validation.
- Business event dispatch.

---

## 2. Directory Access, File Locking & Concurrent Access Semantics

### 2.1 The Challenge: Windows File Sharing vs. POSIX Descriptors
When Frontier Developments (FDev) runs on Windows, the game engine opens journal log files (`Journal.*.log`) with append mode and shared read (`FILE_SHARE_READ`). However, snapshot files (`Status.json`, `Market.json`) are frequently reopened with truncate/write flags.

If external tools attempt to access files without proper sharing flags, the Windows kernel rejects the open call with:
```text
PermissionError: [WinError 32] The process cannot access the file because it is being used by another process.
```

### 2.2 Analysis of Reference Implementation (EDMarketConnector)
In [monitor.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/monitor.py#L375) and [dashboard.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/dashboard.py#L182), EDMC performs:
```python
# Journal opening (unbuffered binary read):
loghandle = open(logfile, "rb", 0)

# Snapshot opening:
with open(status_json_path, "rb") as h:
    data = h.read().strip()
```
- **How EDMC avoids locks:** EDMC does **not** invoke low-level Win32 `CreateFileW` calls. Instead, it relies on Python's standard C runtime (CRT) `open(..., 'rb')`.
- In modern Python (3.10+) on Windows, the underlying MSVCRT implementation of `open()` in read mode requests read sharing (`FILE_SHARE_READ | FILE_SHARE_WRITE`), permitting concurrent access alongside FDev's append/write operations.
- However, for snapshot files (`Status.json`), EDMC occasionally hits sharing collisions or zero-byte buffers during in-place truncation. EDMC mitigates this simply by wrapping reads in `try...except Exception:` blocks, catching errors silently, and waiting for the next 1-second polling iteration.

### 2.3 Evaluated Solution Options for Directory & File Access

#### Option A: Standard Library Ephemeral Read with Transient Retry (Recommended)
- **Mechanism**:
  - Open files using Python standard `open(path, 'rb')`.
  - For streaming journals, maintain an open handle with non-blocking line reading.
  - For snapshots, open, read complete bytes, and immediately close handle (`path.read_bytes()`).
  - Guard transient `PermissionError` (sharing violation) or `JSONDecodeError` (truncation race) with bounded exponential backoff (e.g., 20ms, 40ms, 80ms; up to 3 retries).
- **Pros**: Clean, cross-platform standard library code; zero C-extension or platform dependency.
- **Cons**: Relies on retry backoff rather than deterministic lock coordination.

#### Option B: Low-Level Win32 `_winapi.CreateFile` with Explicit `FILE_SHARE_*` Flags
- **Mechanism**:
  - On Windows, bypass `open()` and call `_winapi.CreateFile(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, ...)`.
  - Wrap handle into C file descriptor via `msvcrt.open_osfhandle()` and `os.fdopen()`.
- **Pros**: Explicit, deterministic kernel sharing flags directly matching Win32 SDK.
- **Cons**: High platform coupling; introduces divergent Windows/POSIX I/O drivers for file opening; unnecessary given modern CRT read behavior.

#### Recommendation
Adopt **Option A**. Standard library `open(..., 'rb')` provides full read-sharing compatibility when combined with an exponential backoff retry guard.

---

## 3. Consideration 1: Divergent OS Flows & Propagation of Platform Context

```mermaid
flowchart TD
    subgraph Path_Discovery ["Path Discovery (Coordinator)"]
        A[SupportedPlatform.from_current_platform] -->|sys.platform| B{Platform?}
        B -->|win32| C[WindowsPathStrategy]
        B -->|linux| D[LinuxProtonPathStrategy]
        C --> E[DiscoveryResult: resolved_path + platform]
        D --> E
    end

    subgraph FPFD_Ingestion ["File Presence & Freshness Detection (Unified)"]
        E --> F[SessionContext / WatcherConfig]
        F --> G[Unified Hybrid Event Driver]
        G --> H{OS Notification?}
        H -->|Event Fired| I[Immediate Freshness Evaluation]
        H -->|1.0s Timeout| I
        I --> J[Stream Journal / Read Snapshot]
    end
```

### Architectural Resolution: Where Divergence is Confined
The platform context must not leak across business logic. We propagate the operating system context cleanly through the following architecture:

1. **Model Enrichment in `DiscoveryResult`**:
   Currently, `DiscoveryResult` ([models.py](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/packages/ed_watcher/discovery/models.py#L29-L34)) stores `(resolved_path, discovery_source)`.
   We enrich `DiscoveryResult` (or create `WatcherSessionConfig`) to carry the resolved `platform: SupportedPlatform`.
2. **Unified Outer Abstraction**:
   The `WatcherPort` contract remains $100\%$ unified:
   ```
   PathDiscoverer -> FilePresenceDetector -> FreshnessChecker -> Stream/ReadAdapter
   ```
3. **Driver Confinement**:
   Platform divergence is confined strictly to:
   - **Path Resolution** (already decoupled in `packages/ed_watcher/discovery/strategies/`).
   - **Filesystem Event Driver Setup**: If running on Linux/Proton over potential network or Wine mount points where `inotify` may drop events, the hybrid event driver shortens its liveness timeout tick (e.g. 500ms instead of 1000ms). The ingestion engine itself executes identical logic across all platforms.

---

## 4. Consideration 2: Execution Order of File Ingestion

```mermaid
sequenceDiagram
    autonumber
    participant Engine as TelemetryEngine
    participant Watcher as WatcherPort (FPFD)
    participant Disk as Saved Games Directory
    participant Domain as Domain Pipeline

    Note over Engine,Domain: Phase 1: Boot & Catch-Up Phase
    Engine->>Watcher: start()
    Watcher->>Disk: Scan & Regex Filter candidate Journal files
    Watcher->>Disk: Select initial active Journal (Candidate Selection Strategy)
    Watcher->>Disk: Open stream & read lines (Offset 0 -> EOF)
    Watcher->>Domain: Replay historical events -> Establish SessionContext (Cmdr, FID, session_start)
    Watcher->>Disk: Checkpoint last_valid_offset = tell()
    Watcher->>Disk: Read Status.json (Verify timestamp >= session_start)
    Watcher->>Domain: Reconcile initial HUD/Cockpit state

    Note over Engine,Domain: Phase 2: Steady-State Runtime (Continuous Loop)
    loop Hybrid Watcher Loop (Event Trigger or 1.0s Timeout)
        alt Journal has new bytes (size > offset)
            Watcher->>Disk: Read new appended byte slice
            Watcher->>Domain: Dispatch live journal events
            Watcher->>Watcher: Advance last_valid_offset
        end
        alt Status.json modified (mtime changed & hash changed)
            Watcher->>Disk: Read whole bytes (with retry guard)
            Watcher->>Domain: Dispatch updated StatusEvent
        end
        alt Journal Event triggers Snapshot (e.g. Market, Cargo)
            Watcher->>Disk: Read whole auxiliary snapshot file
            Watcher->>Domain: Dispatch SnapshotEvent
        end
    end
```

### Execution Order Rules:
1. **Journal Precedes Snapshots on Boot**: The active journal must be read before snapshots because `Fileheader`, `Commander`, and `LoadGame` establish the active `SessionContext` (`session_start`, `FID`, `Odyssey`).
2. **Freshness Gating**: Any snapshot whose payload `timestamp < session_start` is discarded as stale residue from a prior session.
3. **Steady-State Priority**:
   - **Priority 1 (High)**: Journal delta stream (real-time telemetry).
   - **Priority 2 (Medium)**: `Status.json` cockpit state changes (~1.0 Hz).
   - **Priority 3 (Reactive)**: Auxiliary snapshots (`Market.json`, `Cargo.json`) read strictly when triggered by corresponding journal events.

---

## 5. Consideration 3: Ingestion Strategy: Full Read vs. Delta Monitoring

| Target File | Ingestion Strategy | Freshness Metric | Rationale |
| :--- | :--- | :--- | :--- |
| **Journal Files (`Journal.*.log`)** | **Delta Stream (Offset Checkpointing)** | `current_size > last_processed_offset` | Append-only logs grow continuously. Re-reading entire files on every append is an $O(N)$ CPU and I/O anti-pattern. |
| **Status Snapshot (`Status.json`)** | **Delta Ingestion via Content Hashing** | `stat().st_mtime` change AND `hash(raw_bytes) != last_hash` | Small file (~1-2 KB), overwritten ~1s. Read in whole, but only dispatched if raw content hash changes. |
| **Event Snapshots (`Market.json`, etc.)** | **One-Shot Whole Read on Trigger** | Triggered by Journal Event AND `file.exists()` | Read completely upon receipt of triggering journal event, dispatched once, and cached. |

---

## 6. Consideration 4: Candidate Selection Strategies for Active Journal

*Note: The choice of candidate selection algorithm is an open architectural decision with multiple viable options.*

### Evaluated Candidate Selection Strategies

#### Strategy 1: Filesystem Creation Time (`os.path.getctime`)
- **Mechanism**: `max(journal_files, key=os.path.getctime)`.
- **Pros**: Direct and simple; historical convention used by EDMC.
- **Cons**:
  - `ctime` is **not portable**: On Windows it means file creation (birth time), while on POSIX/Linux it represents metadata change time (`st_ctime`).
  - Restoring files from archives or cloud sync resets `ctime` out of game chronological order.

#### Strategy 2: Filesystem Modification Time (`os.path.getmtime`)
- **Mechanism**: `max(journal_files, key=os.path.getmtime)`.
- **Pros**: Portable across Windows and POSIX; reflects the file most recently written to.
- **Cons**: An external process, backup tool, or touch utility can update `mtime` on an old journal, causing false selection.

#### Strategy 3: Canonical Filename Timestamp & Part Parsing (Lexicographical Domain Key)
- **Mechanism**:
  Parse the embedded timestamp and part number directly from the filename regex:
  ```python
  def journal_sort_key(filepath: Path) -> tuple[datetime, int]:
      match = JOURNAL_FILE_REGEX.match(filepath.name)
      if match:
          ts = parse_journal_timestamp(match.group("timestamp"))
          part = int(match.group("part"))
          return (ts, part)
      return (datetime.min, 0)
  ```
  Select: `max(journal_files, key=journal_sort_key)`.
- **Pros**:
  - **100% deterministic and portable**: Immune to filesystem metadata corruption, file copying, timezone shifts, and archive restoration.
  - Matches the game engine's true chronological generation order.
- **Cons**: Requires parsing timestamp strings from filenames.

#### Strategy 4: Composite Key (Filename Domain Key with `mtime` Tiebreaker) (Recommended)
- **Mechanism**:
  Sort primarily by `(timestamp, part)` parsed from filename, with `mtime` as a final tiebreaker for malformed filenames.
- **Pros**: Combines domain precision with robust fallback.

---

## 7. Consideration 5: Stream vs. Read Decision: Impact on Flow & Fallback Strategies

### Impact on Flow
- **Journals (Streaming)**:
  - Persistent read-only handle maintained across turns.
  - Non-blocking byte slice reads up to `EOF`.
  - Handle remains open; `last_offset = handle.tell()` is saved after each parsed line.
- **Snapshots (Read in Whole)**:
  - Transient open-read-close lifecycle.
  - Avoids holding persistent locks on files that FDev frequently truncates.

### Fallback & Recovery Strategies
1. **Truncation Race on Snapshots**:
   - Calling `read_bytes()` during an FDev write cycle returns `0` bytes or truncated JSON.
   - *Fallback*: Do not advance freshness state. Retain previous valid snapshot. Execute exponential backoff retry (20ms, 40ms, 80ms).
2. **Incomplete Line Flush on Journal**:
   - The game engine writes a line but has only flushed partial bytes before the watcher reaches `EOF`.
   - *Fallback*: Verify buffer ends in newline (`\n`). If trailing byte is not `\n`, seek back to `last_offset` and yield.
3. **Journal Part Rotation Rollover**:
   - Game client closes `01.log` and opens `02.log`.
   - *Fallback*: When `EOF` is reached on `01.log`, perform directory presence check for successor `02.log`. When detected, drain `01.log` completely, close descriptor, and transition stream to `02.log`.

---

## 8. Tooling & Technology Inventory

| Tool / Library | Status | Role in FPFD Phase | Rationale |
| :--- | :--- | :--- | :--- |
| **`pathlib.Path`** | Existing (Stdlib) | Path normalization & existence checking | Standardized cross-platform path handling. |
| **`re`** | Existing (Stdlib) | Filename regex parsing (`JOURNAL_FILE_REGEX`) | Extracts timestamp, build prefix, and part number. |
| **`hashlib` (BLAKE2b)** | Existing (Stdlib) | Snapshot content hashing | Fast $O(1)$ change detection for `Status.json` raw bytes without JSON deserialization overhead. |
| **`asyncio` / `threading`** | Existing (Stdlib) | Event loop & timeout ticker | Drives the hybrid event-wait + 1.0s timeout polling loop. |
| **`watchdog`** | **New (Proposed)** | OS filesystem event monitoring (`on_created`, `on_modified`) | Native OS notification drivers (`inotify` on Linux, `ReadDirectoryChangesW` on Windows). |
| **`_winapi` / `msvcrt`** | Existing (Stdlib) | Windows-specific low-level verification (if needed) | Available as fallback if standard library file opening requires low-level share flags. |
