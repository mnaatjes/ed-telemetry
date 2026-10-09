"""Abstract ports for inbound telemetry watchers."""

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

# Type aliases for event handlers
# Handlers accept unparsed event envelopes or domain payloads
IngestionEventHandler = Callable[[Any], None]
AuditEventHandler = Callable[[Any], None]


@runtime_checkable
class WatcherPort(Protocol):
    """Contract for inbound file and telemetry watchers."""

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        """Register a callback for raw file ingestion events."""
        ...

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        """Register a callback for watcher operational audit events."""
        ...

    def start(self) -> None:
        """Start listening or polling for telemetry events asynchronously."""
        ...

    def stop(self) -> None:
        """Stop listening or polling and wait for background workers to exit."""
        ...

    @property
    def is_active(self) -> bool:
        """Return True if watcher is actively listening."""
        ...
