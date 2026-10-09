"""Hybrid reactive reactor unifying journals, snapshots, command queues, and audit events."""

from __future__ import annotations

import collections
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from ed_watcher.engine.envelopes import (
    FileIngestionEvent,
    FileKind,
    WatcherAuditAction,
    WatcherAuditEvent,
)
from ed_watcher.engine.freshness import SnapshotFreshnessTracker
from ed_watcher.engine.receiver import (
    ReactorQueueMetrics,
    WatcherHintAction,
    WatcherIngestCommand,
)
from ed_watcher.engine.snapshot_reader import SnapshotReader
from ed_watcher.engine.stream_context import JournalStreamContext
from ed_watcher.engine.tailer import JournalTailer
from ed_watcher.selector import JournalCandidate, JournalSelector, StreamPosition
from ed_watcher.snapshots import SnapshotIdentifier

DEFAULT_QUEUE_CAPACITY = 256
DEFAULT_TICKER_INTERVAL_POSIX = 0.5  # 0.5s on Wine/Linux
DEFAULT_TICKER_INTERVAL_WIN32 = 1.0  # 1.0s on Windows


class WatcherReactor:
    """
    Execution engine driving file ingestion, freshness evaluation,
    part rollover transitions, and event emission.
    """

    def __init__(
        self,
        journal_dir: Path,
        stream_position: StreamPosition = StreamPosition.TAIL,
        queue_capacity: int = DEFAULT_QUEUE_CAPACITY,
        data_listener: Callable[[FileIngestionEvent], None] | None = None,
        audit_listener: Callable[[WatcherAuditEvent], None] | None = None,
    ) -> None:
        self.journal_dir = journal_dir
        self.stream_position = stream_position
        self.queue_capacity = queue_capacity
        self.data_listener = data_listener
        self.audit_listener = audit_listener

        # Subsystems
        self.selector = JournalSelector(journal_dir)
        self.snapshot_identifier = SnapshotIdentifier(journal_dir)
        self.freshness_tracker = SnapshotFreshnessTracker()
        self.tailer = JournalTailer()
        self.snapshot_reader = SnapshotReader(self.freshness_tracker)

        # Active stream state
        self._active_candidate: JournalCandidate | None = None
        self._active_context: JournalStreamContext | None = None

        # Inbound Command Queue
        self._queue: collections.deque[WatcherIngestCommand] = collections.deque(maxlen=queue_capacity)
        self._queue_lock = threading.Lock()
        self._total_enqueued = 0
        self._total_processed = 0
        self._total_dropped = 0
        self._high_water_mark = 0

        # Lifecycle control
        self._running = False
        self._ticker_interval = (
            DEFAULT_TICKER_INTERVAL_WIN32 if sys.platform == "win32" else DEFAULT_TICKER_INTERVAL_POSIX
        )

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_context(self) -> JournalStreamContext | None:
        return self._active_context

    def _emit_data(self, event: FileIngestionEvent) -> None:
        if self.data_listener is not None:
            self.data_listener(event)

    def _emit_audit(self, action: WatcherAuditAction, target_path: Path, detail: str = "") -> None:
        event = WatcherAuditEvent(
            timestamp=datetime.now(UTC),
            action=action,
            target_path=target_path,
            detail=detail,
        )
        if self.audit_listener is not None:
            self.audit_listener(event)

    def submit_hint(self, command: WatcherIngestCommand) -> bool:
        """Enqueue an operational hint. Returns True if accepted, False if dropped."""
        with self._queue_lock:
            if len(self._queue) >= self.queue_capacity and not command.priority:
                self._total_dropped += 1
                self._emit_audit(
                    WatcherAuditAction.HINT_DROPPED,
                    self.journal_dir,
                    f"Queue saturated; dropped command: {command.action}",
                )
                return False

            self._queue.append(command)
            self._total_enqueued += 1
            depth = len(self._queue)
            if depth > self._high_water_mark:
                self._high_water_mark = depth

            self._emit_audit(
                WatcherAuditAction.HINT_ENQUEUED,
                self.journal_dir,
                f"Enqueued hint: {command.action} ({command.target_name})",
            )
            return True

    def get_queue_metrics(self) -> ReactorQueueMetrics:
        with self._queue_lock:
            return ReactorQueueMetrics(
                current_depth=len(self._queue),
                capacity=self.queue_capacity,
                high_water_mark=self._high_water_mark,
                total_enqueued=self._total_enqueued,
                total_processed=self._total_processed,
                total_dropped=self._total_dropped,
            )

    def start(self) -> None:
        """Initialize active journal stream and transition to running state."""
        self._running = True

        # Discover initial active journal
        active_cand = self.selector.get_active_journal()
        if active_cand is None:
            self._emit_audit(
                WatcherAuditAction.EMPTY_CANDIDATE_SET,
                self.journal_dir,
                "No journal files found at startup; waiting for game creation",
            )
            self._active_candidate = None
            self._active_context = None
        else:
            self._bind_new_journal(active_cand, position=self.stream_position)

    def stop(self) -> None:
        """Finalize and close active stream handles."""
        self._running = False
        if self._active_context is not None:
            self._active_context.close()
            self._active_context = None
        self._active_candidate = None

    def _bind_new_journal(self, candidate: JournalCandidate, position: StreamPosition) -> None:
        """Instantiate and bind a new JournalStreamContext."""
        context = JournalStreamContext.open(candidate.path, part=candidate.part, position=position)
        self._active_candidate = candidate
        self._active_context = context
        self._emit_audit(
            WatcherAuditAction.SELECTED,
            candidate.path,
            f"Bound active journal stream (part={candidate.part}, position={position})",
        )

    def _check_and_handle_rollover(self) -> None:
        """Check if a successor journal has spawned; execute drain-before-switch guarantee."""
        if self._active_candidate is None:
            cand = self.selector.get_active_journal()
            if cand is not None:
                self._bind_new_journal(cand, position=StreamPosition.HEAD)
            return

        successor = self.selector.get_successor(self._active_candidate)
        if successor is not None:
            # 1. Drain trailing bytes on old context
            if self._active_context is not None:
                drain_events, drain_audits = self.tailer.step(self._active_context)
                for ev in drain_events:
                    self._emit_data(ev)
                for au in drain_audits:
                    self._emit_audit(au.action, au.target_path, au.detail)

                # 2. Close retired handle
                old_path = self._active_context.target_path
                self._active_context.close()

                self._emit_audit(
                    WatcherAuditAction.PART_ROLLOVER,
                    successor.path,
                    f"Rotated from {old_path.name} to {successor.filename}",
                )

            # 3. Bind successor unconditionally at StreamPosition.HEAD
            self._bind_new_journal(successor, position=StreamPosition.HEAD)

    def step_once(self) -> Sequence[FileIngestionEvent]:
        """
        Execute one complete tick cycle:
        1. Process inbound hints from queue.
        2. Check journal rollover / drain.
        3. Tail active journal slice.
        4. Read Status.json heartbeat.
        5. Read any available auxiliary snapshots.
        """
        emitted_events: list[FileIngestionEvent] = []

        # 1. Process inbound command queue
        command: WatcherIngestCommand | None = None
        with self._queue_lock:
            if self._queue:
                command = self._queue.popleft()
                self._total_processed += 1

        if command:
            self._emit_audit(
                WatcherAuditAction.HINT_DISPATCHED,
                self.journal_dir,
                f"Dispatched hint: {command.action} ({command.target_name})",
            )
            if command.action == WatcherHintAction.HINT_SNAPSHOT and command.target_name:
                cand = self.snapshot_identifier.resolve_auxiliary(command.target_name)
                if cand:
                    ev, audits = self.snapshot_reader.read_snapshot(cand.resolved_path, FileKind.SNAPSHOT)
                    for a in audits:
                        self._emit_audit(a.action, a.target_path, a.detail)
                    if ev:
                        self._emit_data(ev)
                        emitted_events.append(ev)
            elif command.action == WatcherHintAction.HINT_ROLLOVER:
                self._check_and_handle_rollover()

        # 2. Check for journal rollover or new files
        self._check_and_handle_rollover()

        # 3. Step active journal tailer
        if self._active_context is not None:
            journal_events, journal_audits = self.tailer.step(self._active_context)
            for a in journal_audits:
                self._emit_audit(a.action, a.target_path, a.detail)
            for ev in journal_events:
                self._emit_data(ev)
                emitted_events.append(ev)

        # 4. Step Status.json heartbeat
        status_cand = self.snapshot_identifier.resolve_status()
        if status_cand:
            status_ev, status_audits = self.snapshot_reader.read_snapshot(status_cand.resolved_path, FileKind.STATUS)
            for a in status_audits:
                self._emit_audit(a.action, a.target_path, a.detail)
            if status_ev:
                self._emit_data(status_ev)
                emitted_events.append(status_ev)

        # 5. Step auxiliary snapshots
        for aux_cand in self.snapshot_identifier.resolve_all_available():
            if aux_cand.canonical_name != "Status.json":
                aux_ev, aux_audits = self.snapshot_reader.read_snapshot(aux_cand.resolved_path, FileKind.SNAPSHOT)
                for a in aux_audits:
                    self._emit_audit(a.action, a.target_path, a.detail)
                if aux_ev:
                    self._emit_data(aux_ev)
                    emitted_events.append(aux_ev)

        return tuple(emitted_events)
