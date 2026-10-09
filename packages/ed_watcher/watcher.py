"""Inbound filesystem watcher adapter implementing WatcherPort."""

import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from ed_domain.ports.watcher import AuditEventHandler, IngestionEventHandler, WatcherPort

from ed_watcher.discovery import PathDiscoverer
from ed_watcher.engine.envelopes import FileIngestionEvent, WatcherAuditAction, WatcherAuditEvent
from ed_watcher.engine.reactor import WatcherReactor
from ed_watcher.selector import StreamPosition
from ed_watcher.snapshots.registry import SnapshotRegistry

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
    def journal_dir(self) -> Path | None:
        """Return the active journal directory path, or None if uninitialized."""
        with self._lock:
            return self._journal_dir

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

        for handler in handlers:
            try:
                handler(event)
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

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error("Error in WatcherAuditEvent handler %s: %s", handler, exc)


# Backwards compatibility alias
JournalWatcher = FileSystemWatcher
