"""Unit tests for FileSystemWatcher driving adapter and WatcherPort lifecycle."""

import time
from pathlib import Path
from typing import Any

from domain.ports.watcher import WatcherPort
from infrastructure.watcher.engine.envelopes import FileIngestionEvent, FileKind, WatcherAuditEvent
from infrastructure.watcher.selector import StreamPosition
from infrastructure.watcher.watcher import FileSystemWatcher, JournalWatcher


class TestFileSystemWatcherContractAndProperties:
    """Validate interface conformance, constructor properties, and registration."""

    def test_satisfies_watcher_port_protocol(self) -> None:
        """Verify FileSystemWatcher and JournalWatcher satisfy runtime WatcherPort protocol."""
        watcher = FileSystemWatcher()
        assert isinstance(watcher, WatcherPort)
        assert isinstance(JournalWatcher(), WatcherPort)
        assert not watcher.is_active

    def test_registration_adds_event_and_audit_handlers(self) -> None:
        """Verify register_event_handler and register_audit_handler append unique callbacks."""
        watcher = FileSystemWatcher()
        events_received: list[Any] = []
        audits_received: list[Any] = []

        def event_cb(ev: Any) -> None:
            events_received.append(ev)

        def audit_cb(aud: Any) -> None:
            audits_received.append(aud)

        watcher.register_event_handler(event_cb)
        watcher.register_audit_handler(audit_cb)
        # Duplicate registration should be deduplicated
        watcher.register_event_handler(event_cb)
        watcher.register_audit_handler(audit_cb)

        assert len(watcher._event_handlers) == 1
        assert len(watcher._audit_handlers) == 1


class TestFileSystemWatcherLifecycleAndDispatch:
    """Validate thread execution, background loop, event delivery, and shutdown."""

    def test_start_and_stop_lifecycle_idempotence(self, tmp_path: Path) -> None:
        """Verify starting and stopping cleanly transitions thread state and is idempotent."""
        # Create an initial journal file so reactor starts cleanly
        journal_file = tmp_path / "Journal.2026-10-09T010000.01.log"
        journal_file.write_text('{"event":"Fileheader","part":1}\n', encoding="utf-8")

        watcher = FileSystemWatcher(
            journal_dir=tmp_path,
            poll_interval=0.1,
            join_timeout=2.0,
        )

        assert not watcher.is_active
        watcher.start()
        assert watcher.is_active
        # Calling start again while active is a no-op
        watcher.start()
        assert watcher.is_active

        watcher.stop()
        assert not watcher.is_active
        # Calling stop again is a no-op
        watcher.stop()
        assert not watcher.is_active

    def test_dispatches_file_ingestion_and_audit_events_to_handlers(self, tmp_path: Path) -> None:
        """Verify FileIngestionEvent and WatcherAuditEvent are dispatched to callbacks."""
        journal_file = tmp_path / "Journal.2026-10-09T010000.01.log"
        journal_file.write_text('{"event":"Fileheader","part":1}\n', encoding="utf-8")

        status_file = tmp_path / "Status.json"
        status_file.write_text('{"event":"Status","Flags":0}\n', encoding="utf-8")

        received_events: list[FileIngestionEvent] = []
        received_audits: list[WatcherAuditEvent] = []

        watcher = FileSystemWatcher(
            journal_dir=tmp_path,
            stream_position=StreamPosition.HEAD,  # Read from start
            poll_interval=0.05,
            on_event=lambda ev: received_events.append(ev),
            on_audit=lambda aud: received_audits.append(aud),
            join_timeout=2.0,
        )

        watcher.start()

        # Wait up to 1.5s for initial ingestion events to be processed
        start_time = time.time()
        while time.time() - start_time < 1.5:
            if len(received_events) >= 2:
                break
            time.sleep(0.05)

        # Append a new journal line
        with journal_file.open("a", encoding="utf-8") as fp:
            fp.write('{"event":"Commander","Name":"Jameson"}\n')
            fp.flush()

        # Wait up to 1.0s for appended line
        start_time = time.time()
        while time.time() - start_time < 1.0:
            if len(received_events) >= 3:
                break
            time.sleep(0.05)

        watcher.stop()

        assert any(e.file_kind == FileKind.JOURNAL for e in received_events)
        assert any(e.file_kind == FileKind.STATUS for e in received_events)
        assert len(received_audits) > 0

    def test_exception_in_handler_does_not_crash_watcher_worker(self, tmp_path: Path) -> None:
        """Verify consumer handler exceptions are shielded and do not terminate worker thread."""
        journal_file = tmp_path / "Journal.2026-10-09T010000.01.log"
        journal_file.write_text('{"event":"Fileheader","part":1}\n', encoding="utf-8")

        faulty_calls: list[int] = []
        healthy_events: list[FileIngestionEvent] = []

        def broken_handler(event: FileIngestionEvent) -> None:
            faulty_calls.append(1)
            raise RuntimeError("Consumer crashed!")

        def healthy_handler(event: FileIngestionEvent) -> None:
            healthy_events.append(event)

        watcher = FileSystemWatcher(
            journal_dir=tmp_path,
            stream_position=StreamPosition.HEAD,
            poll_interval=0.05,
            on_event=broken_handler,
            join_timeout=2.0,
        )
        watcher.register_event_handler(healthy_handler)

        watcher.start()

        start_time = time.time()
        while time.time() - start_time < 1.0:
            if len(healthy_events) >= 1:
                break
            time.sleep(0.05)

        watcher.stop()

        assert len(faulty_calls) >= 1
        assert len(healthy_events) >= 1
