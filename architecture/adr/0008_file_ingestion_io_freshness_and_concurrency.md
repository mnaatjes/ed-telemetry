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
   - Open persistent handle in read-only binary mode.
   - Slices are read from `last_valid_offset` up to current EOF.
   - If buffer does not terminate in `\n`, seek back to `last_valid_offset` and await next flush.
2. **Snapshot Whole-Read Mode**:
   - Ephemeral `read_bytes()` with retry guard:
     ```python
     for attempt in range(3):
         raw = path.read_bytes().strip()
         if raw:
             break
         sleep(0.02 * (2**attempt))
     ```
   - Content hash comparison: `hashlib.blake2b(raw, digest_size=8)`.
3. **I/O Envelope Output**:
   Emits `FileIngestionEvent(event_id, timestamp, file_kind, target_path, raw_payload, start_offset, end_offset, part, raw_hash)` where `file_kind: FileKind` (`JOURNAL`, `STATUS`, `SNAPSHOT`).

---

## 5. Consequences

### Positive
* **Zero Collision**: Standard library binary mode provides clean read-sharing without Win32 lock collisions.
* **Truncation Immune**: Transient 0-byte reads during FDev snapshot writes are caught and resolved by retry backoff.
* **Decoupled Architecture**: Domain layer receives raw unparsed bytes in a uniform event envelope without coupling I/O to game schemas.

### Negative
* Requires managing persistent file descriptor lifecycles for active journals across session rotations.
