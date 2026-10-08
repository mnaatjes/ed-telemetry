---
title: "ADR 0008: File Ingestion I/O, Freshness Detection, and Concurrency Guards"
status: "proposed"
date: "2026-10-08"
tags: ["architecture", "adr", "watcher", "ingestion", "freshness", "io", "madr"]
---

# ADR 0008: File Ingestion I/O, Freshness Detection, and Concurrency Guards

## 1. Context and Problem Statement

Following candidate identification for journals ([ADR 0006](0006_active_journal_candidate_selection_and_sorting.md)) and snapshots ([ADR 0007](0007_status_and_snapshot_file_identification.md)), `ed_watcher` must physically open files, evaluate if new unread content exists, and extract raw bytes into the domain pipeline.

In *Elite Dangerous*, target files fall into two distinct physical I/O categories:
1. **Journal Files (`Journal.*.log`)**: Growing, append-only line-delimited streams.
2. **Snapshot Files (`Status.json`, `Market.json`, etc.)**: Overwrite-in-place state files rewritten periodically or upon UI interaction.

These files present severe operational concurrency challenges:
- **Truncation Race Conditions**: FDev rewrites snapshot files by truncating to 0 bytes before writing new JSON, causing external tools to read empty or partially written files.
- **File Locking on Windows**: The game engine opens files with shared read (`FILE_SHARE_READ`). External tools attempting exclusive locks trigger `PermissionError: [WinError 32]`.
- **Incomplete Flushes**: Tailers reading an appending journal stream at EOF may read half a line if the game engine has not yet flushed the trailing newline (`\n`).

We require an architectural decision governing file access modes, freshness metrics, retry concurrency guards, and the boundary envelope for extracted data.

---

## 2. Decision Drivers

* **Scope Purity (FPFD Boundary):** The I/O ingestion engine must remain completely agnostic to JSON business schemas (no parsing of `flags`, `pips`, `fuel`). It extracts raw byte slices.
* **Zero Lock Collisions:** Reading must never interfere with the game engine's write routines on Windows or POSIX.
* **Race Condition Resilience:** In-progress truncations and partial buffer flushes must never crash the engine or advance offsets prematurely.
* **Performance Efficiency:** Append-only journals must be tailed as delta byte streams without re-reading entire multi-megabyte files.

---

## 3. Considered Options

* **Option 1: Read All Files in Whole on Every Change [REJECTED]**
  - Reading entire files into memory works for small snapshots (~1 KB), but causes severe $O(N)$ CPU and disk overhead when applied to growing 100 MB+ journal files.
* **Option 2: Low-Level Win32 `_winapi.CreateFile` Sharing Drivers [REJECTED]**
  - Explicit Win32 handle creation provides granular control, but introduces unnecessary C-extension divergence between Windows and Linux.
* **Option 3: Dual-Mode I/O Engine with Transient Retry Guard (Recommended)**
  - **Journals**: Persistent binary stream tailer (`open(..., 'rb')`). Tracks `last_valid_offset = handle.tell()`. Verifies newline flush before advancing.
  - **Snapshots**: Ephemeral whole-byte reads (`path.read_bytes()`) wrapped in a zero-byte and JSON-decode retry guard with exponential backoff (20ms, 40ms, 80ms).
  - **Freshness**: Hashing snapshot raw bytes via BLAKE2b ($O(1)$) to discard unchanged payloads.
  - **Envelope Model**: Emits a consolidated `FileIngestionEvent` carrying raw unparsed payload.

---

## 4. Decision Outcome

Chosen Option: **Option 3: Dual-Mode I/O Engine with Transient Retry Guard.**

### Architectural Specification

1. **Journal Streaming Mode**:
   - Open persistent handle in read-only binary mode (`open(..., 'rb')`).
   - **Monotonic Forward Seek Invariant**: Seek directly to absolute forward position via `handle.seek(last_valid_offset, os.SEEK_SET)`. Relative seek arithmetic using end-of-file offsets (e.g. `seek(-diff, SEEK_END)` seen in `ed-scout`) is **strictly prohibited**, as concurrent game writes or file rotations trigger negative offset arithmetic, dropping lines or throwing fatal `OSError: [Errno 22] Invalid argument` exceptions.
   - Slices are read from `last_valid_offset` up to current EOF using a 64 KB read buffer to efficiently process startup burst flushes (`Journal.FastWritesOnStartup.log`).
   - If the trailing slice does not terminate in a newline (`\n`), the incomplete fragment is held in memory, and the file pointer is repositioned to `last_valid_offset` to await the next complete flush without advancing state.
   - Tracks line count monotonically (`1`-indexed) to pair line numbers with byte offsets.
2. **Snapshot Whole-Read Mode & Concurrency Mitigations**:
   - **Atomic Read with Structural Boundary Check**: Reads full bytes via `path.read_bytes().strip()`.
   - **Truncation & Interleaved Read Guard**: Validates that bytes are non-empty (`len(raw) > 0`) and conform to JSON structural delimiters (starts with `{` and ends with `}`). If incomplete, retries with exponential backoff (20ms, 40ms, 80ms; up to 3 attempts).
   - **Per-Tier Debouncing**: Implements a 20ms debouncing window to coalesce rapid successive `on_modified` events and poll sweeps, preventing interleaved concurrent read operations on the same snapshot file.
3. **Centralized Deduplication & Freshness Gate (`SnapshotFreshnessTracker`)**:
   - All three trigger tiers (Tier 1 Journal event, Tier 2 Watchdog FS event, Tier 3 Polling tick) must pass through a single serialized deduplication gate before emitting an event.
   - Calculates 64-bit BLAKE2b hash of raw bytes: `current_hash = hashlib.blake2b(raw, digest_size=8).hexdigest()`.
   - Compares against `last_known_hash[snapshot_name]`. If hash matches, the read is discarded as duplicate/unchanged without downstream emission.
4. **I/O Envelope Output**:
   Emits `FileIngestionEvent`:
   ```python
   class FileIngestionEvent(BaseModel):
       event_id: UUID
       timestamp: datetime  # UTC ISO 8601
       file_kind: FileKind  # JOURNAL, STATUS, SNAPSHOT
       target_path: Path
       raw_payload: bytes
       start_offset: int
       end_offset: int
       line_number: int | None  # 1-indexed for journals; None for whole snapshots
       part: int
       raw_hash: str  # 64-bit BLAKE2b
   ```

---

## 5. Consequences

### Positive
* **Zero Collision**: Standard library binary mode provides clean read-sharing without Win32 lock collisions.
* **Truncation Immune**: Transient 0-byte reads during FDev snapshot writes are caught and resolved by retry backoff.
* **Decoupled Architecture**: Domain layer receives raw unparsed bytes in a uniform event envelope without coupling I/O to game schemas.

### Negative
* Requires managing persistent file descriptor lifecycles for active journals across session rotations.
