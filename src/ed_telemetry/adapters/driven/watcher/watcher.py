"""Inbound filesystem watcher adapter implementing WatcherPort."""

import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from ed_telemetry.adapters.driven.watcher.discovery import PathDiscoverer
from ed_telemetry.adapters.driven.watcher.discovery.models import SupportedPlatform
from ed_telemetry.adapters.driven.watcher.engine.envelopes import (
    FileIngestionEvent,
    FileKind,
    WatcherAuditAction,
    WatcherAuditEvent,
)
from ed_telemetry.adapters.driven.watcher.engine.reactor import WatcherReactor
from ed_telemetry.adapters.driven.watcher.engine.receiver import (
    WatcherHintAction,
    WatcherIngestHint,
)
from ed_telemetry.adapters.driven.watcher.engine.snapshot_reader import SnapshotReader
from ed_telemetry.adapters.driven.watcher.selector import JournalSelector, StreamPosition
from ed_telemetry.adapters.driven.watcher.snapshots import SnapshotIdentifier
from ed_telemetry.adapters.driven.watcher.snapshots.registry import SnapshotRegistry
from ed_telemetry.core.ports.driven import (
    AuditEventHandler,
    IngestionEventHandler,
    WatcherPort,
)
from ed_telemetry.core.ports.dto.telemetry_dto import (
    AuxiliarySnapshotDTO,
    FileIngestionEventDTO,
    GameStatusSnapshotDTO,
    HintSubmissionDTO,
    JournalCandidateDTO,
    JournalFileListDTO,
    JournalPathDTO,
    WatcherAuditEventDTO,
)

logger = logging.getLogger(__name__)


class FileSystemWatcher(WatcherPort):
    """Concrete driving adapter monitoring journals and snapshots from the filesystem.

    Orchestrates PathDiscoverer, JournalSelector, SnapshotIdentifier, and WatcherReactor
    inside a managed background daemon worker thread. Dispatches raw FileIngestionEvents
    and WatcherAuditEvents to registered callback handlers.
    """

    def __init__(
        self,
        journal_dir: Path | None = None,
        snapshot_registry: SnapshotRegistry | None = None,
        stream_position: StreamPosition = StreamPosition.TAIL,
        poll_interval: float | None = None,
        on_event: IngestionEventHandler | None = None,
        on_audit: AuditEventHandler | None = None,
        join_timeout: float = 5.0,
    ) -> None:
        self._journal_dir = journal_dir
        self._snapshot_registry = snapshot_registry or SnapshotRegistry()
        self._stream_position = stream_position
        self._poll_interval = poll_interval
        self._join_timeout = join_timeout

        self._event_handlers: list[IngestionEventHandler] = []
        self._audit_handlers: list[AuditEventHandler] = []

        if on_event is not None:
            self._event_handlers.append(on_event)
        if on_audit is not None:
            self._audit_handlers.append(on_audit)

        self._thread: threading.Thread | None = None
        self._reactor: WatcherReactor | None = None
        self._is_active = False
        self._lock = threading.RLock()

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        """Register a callback for raw file ingestion events."""
        with self._lock:
            if handler not in self._event_handlers:
                self._event_handlers.append(handler)

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        """Register a callback for watcher operational audit events."""
        with self._lock:
            if handler not in self._audit_handlers:
                self._audit_handlers.append(handler)

    def start(self) -> None:
        """Start listening or polling for telemetry events asynchronously."""
        with self._lock:
            if self._is_active:
                return

            # Resolve journal directory if not explicitly provided
            active_dir = self._journal_dir
            if active_dir is None:
                discoverer = PathDiscoverer()
                discovery_res = discoverer.discover_journal_directory()
                active_dir = discovery_res.resolved_path
                self._journal_dir = active_dir

            self._reactor = WatcherReactor(
                journal_dir=active_dir,
                stream_position=self._stream_position,
                data_listener=self._dispatch_event,
                audit_listener=self._dispatch_audit,
            )

            self._reactor.start()
            self._is_active = True
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="ed-watcher-reactor",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop listening or polling and wait for background workers to exit."""
        reactor_to_stop: WatcherReactor | None = None
        thread_to_join: threading.Thread | None = None

        with self._lock:
            if not self._is_active:
                return
            self._is_active = False
            reactor_to_stop = self._reactor
            thread_to_join = self._thread

        if reactor_to_stop is not None:
            reactor_to_stop.stop()

        if thread_to_join is not None:
            thread_to_join.join(timeout=self._join_timeout)
            if thread_to_join.is_alive():
                logger.warning(
                    "FileSystemWatcher background thread did not exit within %ss",
                    self._join_timeout,
                )

        with self._lock:
            self._reactor = None
            self._thread = None

    @property
    def is_active(self) -> bool:
        """Return True if watcher is actively listening."""
        with self._lock:
            return self._is_active

    @property
    def journal_dir(self) -> str | None:
        """Return the active journal directory path as string, or None if uninitialized."""
        with self._lock:
            return str(self._journal_dir) if self._journal_dir is not None else None

    def discover_path(self, override_path: str | None = None) -> JournalPathDTO:
        """Discover Elite Dangerous journal directory."""
        discoverer = PathDiscoverer()
        res = discoverer.discover_journal_directory(override_path=override_path)
        platform_name = SupportedPlatform.from_current_platform().value
        return JournalPathDTO(
            resolved_path=str(res.resolved_path),
            platform=platform_name,
            discovery_source=res.discovery_source,
        )

    def list_journals(self) -> JournalFileListDTO:
        """List historical and active journal files in chronological order."""
        active_path: Path
        with self._lock:
            if self._journal_dir is None:
                discoverer = PathDiscoverer()
                res = discoverer.discover_journal_directory()
                self._journal_dir = res.resolved_path
            active_path = self._journal_dir

        selector = JournalSelector(active_path)
        candidates = selector.find_candidates()
        active = selector.get_active_journal()

        dtos = tuple(
            JournalCandidateDTO(
                filename=c.filename,
                path=str(c.path),
                timestamp=c.timestamp,
                part=c.part,
                mtime=c.mtime,
                is_standard_format=c.is_standard_format,
            )
            for c in candidates
        )

        return JournalFileListDTO(
            journal_dir=str(active_path),
            candidates=dtos,
            active_journal=active.filename if active is not None else None,
        )

    def read_status_snapshot(self) -> GameStatusSnapshotDTO:
        """Extract and return the latest Status.json snapshot."""
        active_path: Path
        with self._lock:
            if self._journal_dir is None:
                discoverer = PathDiscoverer()
                res = discoverer.discover_journal_directory()
                self._journal_dir = res.resolved_path
            active_path = self._journal_dir

        identifier = SnapshotIdentifier(active_path, registry=self._snapshot_registry)
        candidate = identifier.resolve_status()
        if candidate is None or not candidate.resolved_path.exists():
            return GameStatusSnapshotDTO(
                exists=False,
                target_path=None,
                timestamp=None,
                raw_payload=b"",
                raw_hash=None,
            )

        reader = SnapshotReader()
        ev, _ = reader.read_snapshot(candidate.resolved_path, FileKind.STATUS)
        if ev is None:
            # Fallback direct read if freshness tracker deduped or empty
            raw_bytes = candidate.resolved_path.read_bytes()
            return GameStatusSnapshotDTO(
                exists=True,
                target_path=str(candidate.resolved_path),
                timestamp=datetime.fromtimestamp(candidate.mtime, tz=UTC),
                raw_payload=raw_bytes,
                raw_hash=None,
            )

        return GameStatusSnapshotDTO(
            exists=True,
            target_path=str(ev.target_path),
            timestamp=ev.timestamp,
            raw_payload=ev.raw_payload,
            raw_hash=ev.raw_hash,
        )

    def read_auxiliary_snapshot(self, name: str) -> AuxiliarySnapshotDTO:
        """Extract and return the latest specified auxiliary snapshot."""
        active_path: Path
        with self._lock:
            if self._journal_dir is None:
                discoverer = PathDiscoverer()
                res = discoverer.discover_journal_directory()
                self._journal_dir = res.resolved_path
            active_path = self._journal_dir

        identifier = SnapshotIdentifier(active_path, registry=self._snapshot_registry)
        candidate = identifier.resolve_auxiliary(name)
        if candidate is None or not candidate.resolved_path.exists():
            return AuxiliarySnapshotDTO(
                target_name=name,
                exists=False,
                target_path=None,
                timestamp=None,
                raw_payload=b"",
                raw_hash=None,
            )

        reader = SnapshotReader()
        ev, _ = reader.read_snapshot(candidate.resolved_path, FileKind.SNAPSHOT)
        if ev is None:
            raw_bytes = candidate.resolved_path.read_bytes()
            return AuxiliarySnapshotDTO(
                target_name=candidate.canonical_name,
                exists=True,
                target_path=str(candidate.resolved_path),
                timestamp=datetime.fromtimestamp(candidate.mtime, tz=UTC),
                raw_payload=raw_bytes,
                raw_hash=None,
            )

        return AuxiliarySnapshotDTO(
            target_name=candidate.canonical_name,
            exists=True,
            target_path=str(ev.target_path),
            timestamp=ev.timestamp,
            raw_payload=ev.raw_payload,
            raw_hash=ev.raw_hash,
        )

    def submit_ingest_hint(self, action: str, target_name: str | None = None) -> HintSubmissionDTO:
        """Submit an operational hint to the reactor queue."""
        with self._lock:
            reactor = self._reactor
            if reactor is None:
                return HintSubmissionDTO(
                    action=action,
                    target_name=target_name,
                    accepted=False,
                    detail="Reactor not running; watcher is inactive",
                )

        try:
            hint_action = WatcherHintAction(action)
        except ValueError:
            return HintSubmissionDTO(
                action=action,
                target_name=target_name,
                accepted=False,
                detail=f"Unknown hint action: {action}",
            )

        hint = WatcherIngestHint(action=hint_action, target_name=target_name, priority=True)
        accepted = reactor.submit_hint(hint)
        return HintSubmissionDTO(
            action=action,
            target_name=target_name,
            accepted=accepted,
            detail="Enqueued successfully" if accepted else "Queue saturated; hint dropped",
        )

    def _worker_loop(self) -> None:
        """Background thread target driving the reactor loop."""
        reactor = self._reactor
        if reactor is None:
            return

        interval = self._poll_interval if self._poll_interval is not None else 0.5

        try:
            while True:
                with self._lock:
                    if not self._is_active:
                        break
                reactor.step_once()
                time.sleep(interval)
        except Exception as exc:  # pragma: no cover
            logger.error("Unhandled exception in WatcherReactor loop: %s", exc, exc_info=True)
            if self._journal_dir is not None:
                self._dispatch_audit(
                    WatcherAuditEvent(
                        timestamp=datetime.now(UTC),
                        action=WatcherAuditAction.RETRY_BACKOFF,
                        target_path=self._journal_dir,
                        detail=f"Unhandled exception in WatcherReactor loop: {exc}",
                    )
                )
        finally:
            with self._lock:
                self._is_active = False

    def _dispatch_event(self, event: FileIngestionEvent) -> None:
        """Dispatch FileIngestionEvent to all registered handlers with exception shielding."""
        with self._lock:
            handlers = list(self._event_handlers)

        # Convert to boundary DTO
        dto = FileIngestionEventDTO(
            event_id=event.event_id,
            timestamp=event.timestamp,
            file_kind=event.file_kind.value,
            target_path=str(event.target_path),
            raw_payload=event.raw_payload,
            start_offset=event.start_offset,
            end_offset=event.end_offset,
            line_number=event.line_number,
            part=event.part,
            raw_hash=event.raw_hash,
        )

        for handler in handlers:
            try:
                handler(dto)
            except Exception as exc:
                logger.error("Error in FileIngestionEvent handler %s: %s", handler, exc)
                self._dispatch_audit(
                    WatcherAuditEvent(
                        timestamp=datetime.now(UTC),
                        action=WatcherAuditAction.RETRY_BACKOFF,
                        target_path=event.target_path,
                        detail=f"Handler exception in {handler}: {exc}",
                    )
                )

    def _dispatch_audit(self, event: WatcherAuditEvent) -> None:
        """Dispatch WatcherAuditEvent to all registered handlers with exception shielding."""
        with self._lock:
            handlers = list(self._audit_handlers)

        dto = WatcherAuditEventDTO(
            timestamp=event.timestamp,
            action=event.action.value,
            target_path=str(event.target_path),
            detail=event.detail,
        )

        for handler in handlers:
            try:
                handler(dto)
            except Exception as exc:
                logger.error("Error in WatcherAuditEvent handler %s: %s", handler, exc)


# Backwards compatibility alias
JournalWatcher = FileSystemWatcher
