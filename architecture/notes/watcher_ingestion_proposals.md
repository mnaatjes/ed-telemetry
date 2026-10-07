---
title: "Watcher Ingestion Architecture: Questions, Speculations, and Best-Practice Proposals"
tags: ["watcher", "ingestion", "proposals", "architecture", "best-practices", "file-monitoring"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# Watcher Ingestion Architecture: Questions, Speculations, and Proposals

## 1. Executive Summary

Based on research into Frontier Developments (FDev) *Elite Dangerous* telemetry patterns and EDMarketConnector (EDMC) reference implementations, this document provides systematic evaluations, speculative trade-offs, and recommended best practices for the design of the `ed_watcher` ingestion engine.

---

## 2. Ingestion Strategy Analysis & Proposals

### Question 1: Is `max(journal_files, key=os.path.getctime)` the most reliable procedure? What are best practices for journals vs. snapshots?

#### Diagnostic & Weaknesses of `os.path.getctime`
1. **Platform Divergence**:
   - On **Windows (NTFS)**: `os.path.getctime` returns file **creation time** (birth time).
   - On **Linux / POSIX**: Historically, `ctime` does *not* mean creation time; it represents the **metadata change time** (`st_ctime`, updated by `chmod`, `chown`, renames, or backup tools).
2. **File Part Disruption**:
   - If a journal rolls over from part `01` to `02`, or if an archive extraction or cloud-sync tool restores files, `ctime` or `mtime` values can be modified out of chronological order.
3. **Snapshot Inapplicability**:
   - Snapshots (`Status.json`, `Market.json`, etc.) have static names. They never accumulate rolling files, so `max()` across filenames does not apply to them.

#### Best-Practice Proposal
- **For Journal Files**:
  Use a **Composite Lexicographical & Metadata Sort Key**:
  Because journal filenames follow strict formats (`Journal.YYYY-MM-DDTHHMMSS.NN.log` or `Journal.YYMMDDHHMMSS.NN.log`), the embedded ISO timestamp and part number represent the ground truth of game session order.
  ```python
  def journal_sort_key(filepath: Path) -> tuple[datetime, int, float]:
      # 1. Parse timestamp and part directly from filename regex
      # 2. Fall back to os.path.getmtime(filepath) as secondary tiebreaker
      match = JOURNAL_FILE_REGEX.match(filepath.name)
      if match:
          ts = parse_journal_timestamp(match.group("timestamp"))
          part = int(match.group("part"))
          return (ts, part, filepath.stat().st_mtime)
      return (datetime.min, 0, filepath.stat().st_mtime)
  ```
  This renders journal ordering immune to filesystem metadata resets, file copy operations, and cross-platform POSIX `ctime` anomalies.
- **For Snapshot Files**:
  Target by deterministic path: `saved_games_dir / "Status.json"`. Track staleness via the internal payload `entry["timestamp"]` correlated against active session boundaries.

---

### Question 2: Is `on_created` a reliable trigger? What other OS triggers exist, and which are best practice?

#### Diagnostic & Weaknesses of `on_created` Alone
1. **Missed Writes**: `on_created` only fires when a file is newly allocated. When FDev writes new lines to an active journal, `on_created` **never fires again**; only `on_modified` (or native file advance) occurs.
2. **Truncation False Triggers**: For snapshot files like `Status.json`, the game does not create a new file; it re-opens and truncates the existing one, triggering `on_modified`.
3. **Cross-Platform Inconsistencies**:
   - **Linux inotify**: Reliably produces `IN_CREATE`, `IN_MODIFY`, and `IN_CLOSE_WRITE`.
   - **Windows ReadDirectoryChangesW**: Generates `FILE_ACTION_ADDED` and `FILE_ACTION_MODIFIED`, but batch coalescing under load can drop or merge rapid events.
   - **Proton / Wine (LXC/Host Mounts)**: Filesystem notification events between Wine/Proton and Linux host mounts (e.g. CIFS, Virtio-FS, 9p, or host bind mounts) frequently fail to bubble up inotify events reliably.

#### Best-Practice Proposal
- **Hybrid Event-Driven Watcher with Fallback Heartbeat (Dual-Engine)**:
  1. **Primary**: Register filesystem listeners for both `on_created` (to catch journal rollover `01.log` $\to$ `02.log` or client restart) AND `on_modified` (to signal that new data is buffered).
  2. **Secondary (Liveness Heartbeat)**: Run a non-blocking background poll ticker (e.g. 500ms–1000ms). If the filesystem notification layer is silent, the ticker inspects `stat().st_size` on the active file descriptor. If size has grown, processing resumes immediately.
  3. This ensures sub-second reactivity on native Windows and Linux desktops while remaining 100% resilient under Wine/Proton and headless server container mounts.

---

### Question 3: Should target files be opened and streamed, read in chunks, or read in whole?

#### Architectural Comparison

| Mode | Journal Files (`Journal.*.log`) | Snapshot Files (`*.json`) |
| :--- | :--- | :--- |
| **Stream (Persistent Handle)** | **Recommended**: Keep persistent unbuffered handle open in binary mode (`open(path, 'rb')`). Tail lines as game appends. Track file pointer via `tell()`. | **Anti-pattern**: Snapshots are overwritten/truncated in place; streaming a truncated file leads to stale handles or reading garbage offsets. |
| **Read in Whole (`read()`)** | Inefficient for large journals (50MB–500MB historical logs). | **Recommended**: Open, read complete bytes into memory (`data = path.read_bytes()`), validate non-empty, parse JSON object. |
| **Read in Chunks** | Useful only for initial historical replay or hashing, but line-based streaming (`for line in handle:`) already provides optimized internal chunking in Python runtime. | Unnecessary: Snapshot files are small (typically 1 KB – 64 KB). |

#### Best-Practice Proposal
- **Journals**: **Persistent Stream Tailer**. Open once in read-only binary mode with non-exclusive sharing. Read line-by-line. Retain byte offset `tell()` after every parsed line.
- **Snapshots**: **Atomic Read-in-Whole with Guard**. Read entire file content into memory, strip whitespace, check `len(data) > 0`, and deserialize.

---

### Question 4: Scanning target directory on a regular basis vs. defining triggers and waiting?

#### Comparison & Failure Modes
- **Pure Directory Scanning (Polling)**:
  - *Pros*: Extremely reliable; zero dependency on kernel event APIs or OS drivers.
  - *Cons*: CPU spinning / disk I/O chatter; latency bounded by poll interval (e.g. 1s lag for fast combat events).
- **Pure Trigger-and-Wait (Watchdog / inotify / ReadDirectoryChangesW)**:
  - *Pros*: Instantaneous sub-millisecond dispatch; zero CPU utilization when idle.
  - *Cons*: Fragile across container mounts, Wine boundaries, network drives; deadlocks if kernel event queue overflows.

#### Best-Practice Proposal: The Reactive Hybrid Pattern
- Use **Reactive Triggers as the Accelerator** and **Low-Frequency Polling as the Guarantee**:
  - The watcher blocks on an async event trigger (`asyncio.Event` or threading `Condition`).
  - Native filesystem events immediately set the event, triggering instant reads.
  - A 1-second timeout on the wait ensures that even if OS triggers are dropped or unsupported, the directory and active files are scanned anyway.
  - Cost is near-zero (single stat call per second when idle), providing $100\%$ uptime guarantees.

---

### Question 5: How can buffering be introduced to catch read errors and duplications? What other strategies catch read errors?

#### Proposed Strategies

1. **Byte-Offset Checkpoint Ledger (Journal Stream)**:
   - Instead of re-reading or deduplicating by event ID (which FDev events do not uniformly provide), maintain `(file_path, byte_offset)`.
   - After successfully validating and parsing line $N$, advance `last_valid_offset = handle.tell()`.
   - If an incomplete line is read (e.g. partial write buffer flush before newline), catch `JSONDecodeError`, perform `handle.seek(last_valid_offset)`, and yield until the next write flushes.
2. **Sliding Memory Window / Ring Buffer (Event Deduplication)**:
   - Maintain an in-memory ring buffer of the last $K$ events (e.g. $K = 100$) storing `(timestamp, event_name, hash(payload_subset))`.
   - When game client restarts or historical catch-up occurs, duplicate emissions are suppressed before crossing domain boundaries.
3. **Payload Checksum / Content Hashing (Snapshot Files)**:
   - For `Status.json`, calculate Fast 64-bit hash (e.g. `xxhash` or `hashlib.blake2b(digest_size=8)`) of raw bytes.
   - If `current_hash == last_hash`, discard immediately without invoking JSON deserializer or notifying downstream consumers.

---

### Question 6: How do we avoid race conditions?

#### Identified Races & Defenses

1. **Truncation Race (Snapshot Files)**:
   - *Problem*: Game truncates `Status.json` to 0 bytes before writing new JSON payload. Watcher triggers on truncate event and reads empty file or partial syntax `{"timestamp": "2026...`.
   - *Defense*: **Zero-Byte Guard + Exponential Backoff Retry**:
     ```python
     for attempt in range(max_retries):
         raw = path.read_bytes().strip()
         if raw:
             try:
                 return json.loads(raw)
             except json.JSONDecodeError:
                 pass
         await asyncio.sleep(0.02 * (2**attempt))  # 20ms, 40ms, 80ms
     ```
2. **File Rollover Race (Part Splitting)**:
   - *Problem*: Game stops writing to `Journal.2026-10-07T032501.01.log` and creates `02.log`. Tailer might read EOF on `01.log` and terminate or miss the transition.
   - *Defense*: When reaching EOF on the active journal, perform a directory scan to verify if a successor part (`part + 1`) or newer journal exists before going to sleep. Drain remaining bytes of old file before rotating file handle to the new file.
3. **Cross-Process File Locking (Windows Share Denied)**:
   - *Problem*: Windows game engine opens file with `FILE_SHARE_READ`. If external tool opens with write locks or exclusive read, Windows raises `PermissionError` (Sharing Violation).
   - *Defense*: In Python on Windows, standard `open(..., 'rb')` specifies shared read. On low-level handles, strictly avoid request for write or delete sharing.

---

### Question 7: Best practices for easing out of failures, skipping a broken process, etc.?

#### Proposed Resilience Matrix

1. **Corrupted Line Quarantine (Circuit Breaker / Dead Letter)**:
   - If a specific journal line cannot be decoded after newline termination (e.g. binary garbage or invalid UTF-8):
     - Log diagnostic warning with line number, offset, and corrupted byte slice.
     - Emit a domain `TelemetryQuarantineEvent` to notify observability pipelines.
     - Advance offset to next newline (`\n`) and continue processing. Never crash the long-running watcher process over a single corrupt line.
2. **Supervised Worker Lifecycle (Actor / Task Supervision)**:
   - Encapsulate the file watcher inside an isolated background task/worker with automatic backoff restart:
     - State transitions: `STARTING -> MONITORING -> RECOVERING -> HALTED`.
     - Transient I/O failures (e.g. drive unmounted or permission flicker) trigger `RECOVERING` with exponential backoff (1s, 2s, 4s, up to 30s) instead of process termination.
3. **Graceful Degradation for Auxiliary Snapshots**:
   - If secondary snapshot files (`Market.json`, `FCMaterials.json`) fail to parse or are locked by third-party anti-virus scanners, the watcher logs a degraded warning and allows core journal processing to proceed unhindered.
   - Core game telemetry must never block on auxiliary snapshot availability.
