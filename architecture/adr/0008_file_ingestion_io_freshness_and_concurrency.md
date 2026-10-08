---
title: "ADR 0008: File Ingestion Engine, Concurrency Guards, and Reactive Reactor"
status: "proposed"
date: "2026-10-08"
tags: ["architecture", "adr", "watcher", "ingestion", "freshness", "io", "reactor", "driver", "auditing", "madr"]
---

# ADR 0008: File Ingestion Engine, Concurrency Guards, and Reactive Reactor

## 1. Context and Problem Statement

Following candidate identification for journals ([ADR 0006](0006_active_journal_candidate_selection_and_sorting.md)) and snapshots ([ADR 0007](0007_status_and_snapshot_file_identification.md)), `ed_watcher` requires a unified execution engine to manage file descriptor lifecycles, schedule reactive checks across heterogeneous operating systems, evaluate freshness, and stream raw bytes into the domain pipeline.

In *Elite Dangerous*, target files fall into two distinct physical I/O categories:
1. **Journal Files (`Journal.*.log`)**: Growing, append-only line-delimited streams with session part rollovers.
2. **Snapshot Files (`Status.json`, `Market.json`, etc.)**: Overwrite-in-place state files rewritten periodically or upon UI interaction.

These files present severe operational concurrency and scheduling challenges:
- **Truncation Race Conditions**: FDev rewrites snapshot files by truncating to 0 bytes before writing new JSON, causing external tools to read empty or partially written files.
- **File Locking on Windows**: The game engine opens files with shared read (`FILE_SHARE_READ`). External tools attempting exclusive locks trigger `PermissionError: [WinError 32]`.
- **Incomplete Flushes**: Tailers reading an appending journal stream at EOF may read half a line if the game engine has not yet flushed the trailing newline (`\n`).
- **Proton / Wine Inotify Loss (Empirically Confirmed)**: Empirical research across community codebases confirms that Linux kernel `inotify` events are frequently dropped across Steam Proton/Wine virtual filesystems. In `joncage/ed-scout`, tests verifying watchdog inotify modifications had to be explicitly disabled (`@pytest.mark.skip(reason="unreliable on linux")`), forcing the application to maintain a separate background thread polling `os.stat()` every 100ms.
- **Fault Recovery**: Unreadable files, corrupt byte sequences, or drive unmounts must not crash the long-running application process.

We require a consolidated architectural decision governing file access modes, the reactive event loop (reactor), freshness metrics, concurrency retry guards, session rollover transitions, and the data/audit boundary envelopes.

---

## 2. Decision Drivers

* **Scope Purity (FPFD Boundary):** The I/O ingestion engine must remain completely agnostic to JSON business schemas (no parsing of `flags`, `pips`, `fuel`). It extracts raw byte slices.
* **Continuous Liveness Guarantee:** Telemetry must never stall indefinitely due to dropped kernel filesystem events across Proton/Wine or network mounts.
* **Zero Lock Collisions:** Reading must never interfere with the game engine's write routines on Windows or POSIX.
* **Race Condition Resilience:** In-progress truncations and partial buffer flushes must never crash the engine or advance offsets prematurely.
* **Performance Efficiency:** Append-only journals must be tailed as delta byte streams without re-reading entire multi-megabyte files, and idle monitoring must not spin CPU in tight polling loops.
* **Decoupled Observability:** Operational transitions (discovery, selection, retries, rollovers, quarantine) must be auditable without polluting domain models.

---

## 3. Considered Options

* **Option 1: Pure Polling Loop with Full Re-Reads [REJECTED]**
  - Reading entire files into memory on a static 1-second timer avoids complex event drivers, but causes severe $O(N)$ CPU and disk overhead when applied to growing 100 MB+ journal files and introduces fixed polling latency.
* **Option 2: Low-Level Win32 APIs and Pure Inotify Event Watcher [REJECTED]**
  - Sub-millisecond latency on local desktops, but vulnerable to silent deadlocks if Wine or container mounts drop kernel notification events, and introduces unnecessary platform-divergent C-extension code.
* **Option 3: Unified Dual-Mode I/O Engine with Hybrid Reactive Reactor (Recommended)**
  - **Hybrid Reactor Driver**: Primary reactivity driven by `watchdog` (`on_created`, `on_modified`) with a bounded fallback timeout ticker (1.0s on Windows, 0.5s on Wine/Linux) to guarantee liveness under dropped kernel events.
  - **Journal Tailing**: Persistent binary stream tailer (`open(..., 'rb')`) utilizing monotonic forward seek (`SEEK_SET`) and a 64 KB burst buffer. Verifies newline flush before advancing byte and line offsets.
  - **Snapshot Whole-Read**: Ephemeral whole-byte reads (`path.read_bytes()`) wrapped in a zero-byte and JSON structural delimiter check (`startswith('{') and endswith('}')`) with exponential backoff (20ms, 40ms, 80ms).
  - **Freshness & Deduplication**: Serialized `SnapshotFreshnessTracker` utilizing 64-bit BLAKE2b raw byte hashing to discard unchanged payloads.
  - **Dual Event Envelopes**: Cleanly isolates the Data Plane (`FileIngestionEvent`) from the Operational Control Plane (`WatcherAuditEvent`).

---

## 4. Decision Outcome

Chosen Option: **Option 3: Unified Dual-Mode I/O Engine with Hybrid Reactive Reactor.**

### Architectural Specification

```mermaid
flowchart TD
    subgraph ReactiveReactor["Execution Driver: Hybrid Reactor"]
        W[watchdog FS Events] -->|on_created / on_modified| Signal[Async Wakeup Signal]
        Timer[Bounded Timeout Ticker: 0.5s / 1.0s] --> Signal
        Signal --> Dispatch{Event Dispatcher}
    end

    subgraph IOEngine["I/O & Concurrency Engine"]
        Dispatch -->|Journal Active| JT[Journal Stream Tailer]
        Dispatch -->|Snapshot Trigger| SW[Snapshot Whole-Reader]
        JT -->|Monotonic Forward Seek| JBuf[64 KB Buffer & Newline Verify]
        SW -->|20ms Debounce| SCheck{len > 0 and starts '{' and ends '}'}
        SCheck -->|Truncated / Race| Backoff[Exponential Backoff: 20ms, 40ms, 80ms]
        Backoff --> SW
        SCheck -->|Valid| Hash[SnapshotFreshnessTracker: BLAKE2b 64-bit]
    end

    subgraph EnvelopePlane["Emitted Event Envelopes"]
        JBuf --> FIE[FileIngestionEvent - Data Plane]
        Hash -->|New Hash| FIE
        Hash -->|Identical Hash| Discard[Discard Duplicate]
        Dispatch -.->|Lifecycle Transitions| WAE[WatcherAuditEvent - Control Plane]
    end
```

#### 1. Hybrid Reactive Reactor Loop
* **Event Driver**: Uses `watchdog` registering listeners for `on_created` (rollover detection) and `on_modified` (append notification).
* **Liveness Heartbeat**: Async wait with bounded timeout (`timeout=1.0` on Windows, `timeout=0.5` on Linux/Wine).
* **Wakeup Logic**: If an OS kernel event fires, the reactor wakes immediately; if the timeout expires, the reactor executes a fallback freshness check across active candidates.

#### 2. Journal Streaming Mode & Part Rollover Protocol
* Open persistent handle in read-only binary mode (`open(..., 'rb')`).
* **Monotonic Forward Seek Invariant**: Seek directly to absolute forward position via `handle.seek(last_valid_offset, os.SEEK_SET)`. Relative seek arithmetic using end-of-file offsets (e.g. `seek(-diff, SEEK_END)` seen in `ed-scout`) is **strictly prohibited**, as concurrent game writes or file rotations trigger negative offset arithmetic, dropping lines or throwing fatal `OSError: [Errno 22] Invalid argument` exceptions.
* Slices are read from `last_valid_offset` up to current EOF using a 64 KB read buffer to efficiently process startup burst flushes (`Journal.FastWritesOnStartup.log`).
* If the trailing slice does not terminate in a newline (`\n`), the incomplete fragment is held in memory, and the file pointer is repositioned to `last_valid_offset` to await the next complete flush without advancing state.
* Tracks line count monotonically (`1`-indexed) to pair line numbers with byte offsets.

##### The Continuous Spawn & Stale Handle Retirement Protocol
To prevent endlessly tailing a retired journal file when the game transitions parts or launches a new session, the engine implements a 3-trigger retirement workflow:

1. **Continuous Spawn Awareness**:
   The reactor does not cease directory awareness while tailing an active file. A filesystem `on_created` notification matching `JOURNAL_FILE_REGEX` immediately triggers candidate re-evaluation via ADR 0006 (`get_successor(current_journal)`).
2. **Idle Re-Evaluation Ticker (Anti-Zombie Guard)**:
   If the currently active file handle has been sitting at EOF with zero new bytes read for $\ge 5.0$ seconds (or when an edge-case kernel inotify drop occurs), the periodic fallback ticker executes a fast candidate scan to detect if a newer journal file has spawned unannounced.
3. **Drain-Before-Switch Guarantee**:
   When a successor journal is confirmed:
   - The engine performs one final read on the retired journal descriptor to capture and emit any trailing buffered bytes up to true EOF.
   - The active handle is explicitly closed (`handle.close()`).
   - The engine emits `WatcherAuditEvent(action=PART_ROLLOVER, detail="Rotated from <old> to <new>")`.
   - The file pointer for the new successor journal is bound according to the configured startup positioning (`StreamPosition.HEAD`).
   - The retired file is marked read-only/immutable in the watcher's session tracking and will not be re-scanned.

#### 3. Snapshot Whole-Read Mode & Concurrency Mitigations
* **Atomic Read with Structural Boundary Check**: Reads full bytes via `path.read_bytes().strip()`.
* **Truncation & Interleaved Read Guard**: Validates that bytes are non-empty (`len(raw) > 0`) and conform to JSON structural delimiters (starts with `{` and ends with `}`). If incomplete, retries with exponential backoff (20ms, 40ms, 80ms; up to 3 attempts).
* **Per-Tier Debouncing**: Implements a 20ms debouncing window to coalesce rapid successive `on_modified` events and poll sweeps, preventing interleaved concurrent read operations on the same snapshot file.

#### 4. Centralized Deduplication & Freshness Gate (`SnapshotFreshnessTracker`)
* All three trigger tiers (Tier 1 Journal event, Tier 2 Watchdog FS event, Tier 3 Polling tick) must pass through a single serialized deduplication gate before emitting an event.
* Calculates 64-bit BLAKE2b hash of raw bytes: `current_hash = hashlib.blake2b(raw, digest_size=8).hexdigest()`.
* Compares against `last_known_hash[snapshot_name]`. If hash matches, the read is discarded as duplicate/unchanged without downstream emission.

#### 5. Dual Event Envelope Contracts

##### Data Plane: `FileIngestionEvent`
Emitted upon extracting a valid raw byte slice from disk:
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
    part: int | None
    raw_hash: str  # 64-bit BLAKE2b
```

##### Control & Observability Plane: `WatcherAuditEvent`
Emitted upon internal state transitions, fault mitigations, or operational heartbeats:
```python
class WatcherAuditAction(StrEnum):
    DISCOVERED = "discovered"
    SELECTED = "selected"
    POLL_TICK = "poll_tick"
    FRESHNESS_VERIFIED = "freshness_verified"
    RETRY_BACKOFF = "retry_backoff"
    PART_ROLLOVER = "part_rollover"
    LINE_QUARANTINED = "line_quarantined"
    CASING_COLLISION_DETECTED = "casing_collision_detected"
    EMPTY_CANDIDATE_SET = "empty_candidate_set"
    HINT_RECEIVED = "hint_received"


@dataclass(frozen=True)
class WatcherAuditEvent:
    timestamp: datetime
    action: WatcherAuditAction
    target_path: Path
    detail: str = ""
```

#### 6. Inbound Control Plane Port: `WatcherIngestReceiver` (The Feedback Boundary)

To support event-gated snapshot triggers (ADR 0007 Tier 1) and external rollover hints without violating the Cardinal Boundary (FPFD) or requiring the watcher to parse JSON, the engine exposes a decoupled inbound port:

```python
class WatcherHintAction(StrEnum):
    HINT_SNAPSHOT = "hint_snapshot"  # Request immediate read of specific snapshot
    HINT_ROLLOVER = "hint_rollover"  # Request immediate evaluation for next journal part
    HINT_DIRECTORY_SCAN = "hint_scan"  # Request immediate directory sweep


@dataclass(frozen=True)
class WatcherIngestCommand:
    """
    Agnostic filesystem hint received across the boundary.
    Contains zero game schema logic.
    """

    action: WatcherHintAction
    target_name: str | None = None  # e.g., "Market.json", "NavRoute.json", or None
    priority: bool = False  # Instantly wakes reactor if True


class WatcherIngestReceiver(Protocol):
    """Inbound boundary protocol implemented by the reactive reactor."""

    def submit_hint(self, command: WatcherIngestCommand) -> None:
        """
        Receives an operational hint from external consumers (e.g. downstream parsers),
        enqueues the command, and signals the async reactor loop to wake immediately.
        """
        ...
```

##### Feedback Loop Execution Flow
1. **Signal Ingestion**: Downstream layers (e.g. Phase 2 deserializer or test harness) invoke `submit_hint(command)`.
2. **Reactor Wakeup**: Submitting an interrupt command enqueues the DTO and signals the reactor's async event wait (`asyncio.Event`), instantly breaking the 0.5s/1.0s sleep timer.
3. **Targeted Dispatch**:
   - If `action == HINT_SNAPSHOT`, the reactor delegates `target_name` directly to `SnapshotIdentifier` (ADR 0007), bypassing the timer tick.
   - If `action == HINT_ROLLOVER`, the reactor immediately queries `CandidateSelector.get_successor()` (ADR 0006) to execute the drain-and-switch sequence.
4. **Zero Domain Inversion**: The watcher never decodes or evaluates event payloads; it strictly processes incoming operational file hints.

---

## 5. Consequences

### Positive
* **Unified Architectural Model**: Merges the physical I/O tailer and reactive scheduling loop into a single, cohesive engine specification, eliminating unnecessary manager abstractions.
* **100% Platform Liveness**: Combines sub-millisecond OS event reactivity on native desktops with an active timeout ticker that prevents silent freezes under Proton/Wine or network mounts.
* **Truncation & Race Immunity**: Transient 0-byte states during FDev in-place rewrites are caught and resolved by boundary guards and exponential backoff.
* **Decoupled Observability**: Operational metrics and quarantine events flow through `WatcherAuditEvent` without polluting domain telemetry pipelines.

### Negative
* Requires managing persistent file descriptor lifecycles for active journals across multi-part session rollovers.
* Introduces `watchdog` as a project dependency to handle cross-platform filesystem event drivers.
