---
title: "ADR 0006: Active Journal Candidate Selection and Sorting Strategy"
status: "accepted"
date: "2026-10-08"
tags: ["architecture", "adr", "watcher", "journal", "candidate-selection", "sorting", "madr"]
---

# ADR 0006: Active Journal Candidate Selection and Sorting Strategy

## 1. Context and Problem Statement

Following the resolution of the OS journal directory by `PathDiscoverer` ([ADR 0004](0004_os_path_discovery_and_filesystem_research_framework.md)), the `ed_watcher` subsystem must identify which journal file (`Journal.*.log`) is currently active and requires initial streaming.

In Frontier Developments (FDev) *Elite Dangerous*, journal filenames adhere to strict patterns, but exhibit temporal variances:
- **Odyssey Era (Update 11+ / 4.0 Live)**: `Journal.YYYY-MM-DDTHHMMSS.NN.log` (15-character ISO-like timestamp).
- **Legacy Era (Horizons 3.8 / Beyond)**: `Journal.YYMMDDHHMMSS.NN.log` (12-digit compact timestamp).
- **Test Builds**: Optional `Alpha` or `Beta` build prefixes (e.g. `JournalBeta...`).
- **Session Rollover**: Long play sessions split into sequential parts (`01.log` $\to$ `02.log`) sharing start timestamps or advancing timestamps.

Historical community implementations (e.g. EDMarketConnector) identify the newest file via `max(journal_files, key=os.path.getctime)`. However:
1. `ctime` is **not portable**: On Windows NTFS, `getctime` returns file creation (birth) time, whereas on POSIX/Linux, `st_ctime` represents inode metadata change time (altered by renames, `chmod`, and backup tools).
2. Archive extraction, cloud synchronization, or external file copying can distort filesystem timestamps out of true game chronological order.

We require an architectural decision for how `ed_watcher` filters, sorts, and selects candidate journal files deterministically.

---

## 2. Decision Drivers

* **Deterministic Chronology:** Candidate ranking must strictly reflect the game engine's true chronological generation order.
* **Cross-Platform Portability:** Algorithm behavior must be identical on native Windows NTFS and Linux (Proton/Wine/native).
* **Archive & Copy Resilience:** Restored files or copied logs must not disrupt candidate ordering.
* **Rollover Part Safety:** Part `02.log` must reliably rank above `01.log` when timestamps coincide.
* **Zero Schema Inversion:** Selection must not depend on opening or parsing JSON inside the file.

---

## 3. Considered Options

* **Option 1: Filesystem Creation Time (`os.path.getctime`) (Status Quo)**
  - Direct and simple, but non-portable across OS environments and vulnerable to backup/restore timestamp distortions.
* **Option 2: Filesystem Modification Time (`os.path.getmtime`)**
  - Portable across Windows and POSIX, but external utilities or virus scanners updating `mtime` on historical logs can cause false selection.
* **Option 3: Pure Filename Domain Key Parsing (`JOURNAL_FILE_REGEX`)**
  - Parses `(timestamp, part)` directly from the filename. Highly deterministic, but fails if non-matching or synthetic test logs lack formatted timestamps.
* **Option 4: Composite Lexicographical & Metadata Sort (Recommended)**
  - Combines primary domain filename regex parsing `(timestamp, part)` with filesystem `st_mtime` as a tertiary tiebreaker.

---

## 4. Decision Outcome

Chosen Option: **Option 4: Composite Lexicographical & Metadata Sort.**

### Architectural Specification

1. **Filtering**: All files in the resolved journal directory are filtered strictly against the canonical regex:
   ```python
   JOURNAL_FILE_REGEX = re.compile(
       r"^Journal(?P<build>Alpha|Beta)?"
       r"\.(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{6}|\d{12})"
       r"\.(?P<part>\d{2})"
       r"\.log$",
       re.IGNORECASE,
   )
   ```
2. **Composite Sort Key**:
   ```python
   def composite_journal_sort_key(filepath: Path) -> tuple[datetime, int, float]:
       match = JOURNAL_FILE_REGEX.match(filepath.name)
       if match:
           ts = parse_journal_timestamp(match.group("timestamp"))
           part = int(match.group("part"))
           return (ts, part, filepath.stat().st_mtime)
       return (datetime.min, 0, filepath.stat().st_mtime)
   ```
3. **Selection**:
   ```python
   active_journal = max(candidate_files, key=composite_journal_sort_key)
   ```

### 4.1 Failure and Abort Workflows

1. **Empty Candidate Set (`len(candidate_files) == 0`)**:
   - *Scenario*: The resolved journal directory exists and is accessible, but contains no files matching `JOURNAL_FILE_REGEX` (e.g. fresh game installation before initial launch, or wrong directory).
   - *Behavior*: **Non-Fatal Waiting Transition**.
     - The selector yields `None` (or returns empty candidate result) and emits `WatcherAuditEvent(action=EMPTY_CANDIDATE_SET, detail="No matching journal files found")`.
     - The watcher transitions into `WAITING_FOR_JOURNAL` state and listens for OS `on_created` events or poll ticks. It does **not** raise a fatal exception or abort the engine process.
2. **Directory Inaccessibility / Non-Existence**:
   - *Scenario*: The injected directory path from `PathDiscoverer` does not exist or raises `PermissionError`.
   - *Exception*: Raises `JournalDirectoryAccessError(target_path, reason)` deriving from `WatcherError`. This is an unrecoverable configuration error that halts the watcher startup.
3. **Corrupt Candidate Filenames**:
   - *Scenario*: Candidate matches regex but date/part string extraction produces unparseable values.
   - *Behavior*: `composite_journal_sort_key` catches parsing exceptions, logs a warning, and falls back to `(datetime.min, 0, stat().st_mtime)` so that ingestion is never blocked by a malformed test fixture.

### 4.2 Declarative Startup Stream Positioning

Drawing from streaming architecture established in community references (e.g. `ed-journal`), the journal watcher supports an explicit startup positioning parameter (`StreamPosition`):
1. **`HEAD` (Default for batch/history)**: Begins tailing at byte offset 0 of the active journal file.
2. **`TAIL` (Default for live monitoring)**: Seeks immediately to `st_size` (end of file) upon startup, reading only subsequent events emitted while the daemon is actively running.
3. **`LOCATE_EVENT(event_name)`**: Rapidly scans backwards from end-of-file across candidate journals to locate the last emitted instance of a critical state event (e.g. `Location`, `FSDJump`, `FileHeader`), initializing session state in milliseconds without replaying historical gigabytes of exploration logs.

### 4.3 Proton & Steam Deck Discovery Integration (PathDiscoverer Implementation Update)

> [!NOTE]
> **Superseding Implementation Requirement for `PathDiscoverer`**:
> While `PathDiscoverer` architecture was originally established in [ADR 0004](0004_os_path_discovery_and_filesystem_research_framework.md), empirical research across community codebases (`joncage/ed-scout` and `kayahr/ed-journal`) establishes the definitive canonical Steam Proton path layout on Linux. During concrete implementation of the `packages/ed_watcher.discovery` module, `PathDiscoverer`'s Linux strategy (`LinuxProtonPathStrategy`) must incorporate the concrete Steam App ID heuristic below as a primary candidate path prior to generic Wine prefix probing.

Informed by findings in `ed-scout` (`SavedGamesLocator.py`) and `ed-journal` (`findDirectory`), the candidate search space on Linux platforms must include the canonical Steam Proton Wine prefix for Elite Dangerous:
```text
~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous
```
Where App ID `359320` is the canonical Steam store identifier for *Elite Dangerous*. The resolver must evaluate this path in `PathDiscoverer` fallback sequences before declaring candidate set vacancy.

### 4.4 Continuous Runtime Candidate Re-Evaluation & Successor Ranking

Candidate selection is not solely an initial boot operation; it is an active evaluator invoked throughout the engine's lifecycle:
1. **Dynamic Successor Query (`get_successor(current_journal)`)**:
   When notified of new files or upon idle timeout checks, the selector inspects the journal directory and determines if a strictly newer candidate exists according to `composite_journal_sort_key`.
   - **Part Rollover**: Evaluates whether a candidate with matching session timestamp and higher part number (`part > current_part`) is present.
   - **New Session**: Evaluates whether a candidate with a strictly newer timestamp exists.
2. **Determinism Invariant**:
   The active journal must strictly satisfy:
   ```python
   active_journal = max(candidate_files, key=composite_journal_sort_key)
   ```
   If any candidate ranks higher than the currently tailed file, the selector signals the engine to initiate retirement of the current file handle without blocking or throwing exceptions.

---

## 5. Consequences

### Positive
* **100% Platform Portability**: Eliminates OS divergence between Windows birthtime and POSIX metadata change time.
* **Session Rollover Resilient**: Correctly sequences multi-part files (`01` $\to$ `02`) without race conditions.
* **Graceful Degradation**: Non-standard test files gracefully fall back to `st_mtime`.

### Negative
* Incurs minor regex and datetime string parsing overhead during initial startup directory scan ($O(N)$ once at boot).
