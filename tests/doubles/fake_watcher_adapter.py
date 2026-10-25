"""In-memory test double for WatcherPort."""

from __future__ import annotations

from pathlib import Path

from ed_telemetry.core.ports.driven.telemetry_driven_port import (
    AuditEventHandler,
    FileIngestionEventDTO,
    IngestionEventHandler,
    WatcherAuditEventDTO,
    WatcherPort,
)


class FakeWatcherAdapter(WatcherPort):
    """In-memory test double for WatcherPort satisfying HEXA-TRUTH-27."""

    def __init__(self, journal_dir: Path | None = None) -> None:
        self._journal_dir = journal_dir
        self._is_active = False
        self._event_handlers: list[IngestionEventHandler] = []
        self._audit_handlers: list[AuditEventHandler] = []

    def start(self) -> None:
        """Mark adapter active without OS thread creation."""
        self._is_active = True

    def stop(self) -> None:
        """Mark adapter inactive."""
        self._is_active = False

    @property
    def is_active(self) -> bool:
        """Return active status."""
        return self._is_active

    @property
    def journal_dir(self) -> Path | None:
        """Return journal directory."""
        return self._journal_dir

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        """Register event handler."""
        self._event_handlers.append(handler)

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        """Register audit handler."""
        self._audit_handlers.append(handler)

    def emit_test_event(self, event: FileIngestionEventDTO) -> None:
        """Simulate event emission to all registered handlers."""
        for handler in self._event_handlers:
            handler(event)

    def emit_test_audit(self, event: WatcherAuditEventDTO) -> None:
        """Simulate audit emission to all registered handlers."""
        for handler in self._audit_handlers:
            handler(event)
