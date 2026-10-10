"""Root domain boundary port protocols and reusable capabilities.

Governed by ADR 0015 and SDD-013.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

IngestionEventHandler = Callable[[Any], None]
AuditEventHandler = Callable[[Any], None]


@runtime_checkable
class Port(Protocol):
    """Root marker protocol for all domain boundary ports.

    Serves as the common polymorphic root for structural typing,
    generic container bounds, and reflection audits.
    """


@runtime_checkable
class LifecyclePort(Port, Protocol):
    """Capability protocol for domain ports requiring background execution management."""

    def start(self) -> None:
        """Start background workers or streaming channels asynchronously."""
        ...

    def stop(self) -> None:
        """Gracefully stop and join background workers deterministically."""
        ...

    @property
    def is_active(self) -> bool:
        """Return True if background workers are actively executing."""
        ...


@runtime_checkable
class DiscreteSinkPort(Port, Protocol):
    """Capability protocol for discrete, outbound point-in-time transmission sinks."""

    def send(self, payload: Mapping[str, Any]) -> None:
        """Transmit a payload to downstream consumers."""
        ...


@runtime_checkable
class StreamSourcePort(Port, Protocol):
    """Capability protocol for continuous inbound event streaming sources."""

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        """Register a callback for raw file ingestion events."""
        ...

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        """Register a callback for operational audit events."""
        ...


@runtime_checkable
class ConnectionPort(Port, Protocol):
    """Capability protocol for stateful, persistent network connections."""

    def connect(self) -> None:
        """Establish persistent network connection."""
        ...

    def disconnect(self) -> None:
        """Cleanly close persistent network connection."""
        ...

    @property
    def is_connected(self) -> bool:
        """Return True if persistent connection is active and ready."""
        ...


@runtime_checkable
class TransactionalPort(Port, Protocol):
    """Capability protocol for atomic, scoped persistence resources."""

    def commit(self) -> None:
        """Commit pending changes atomically."""
        ...

    def rollback(self) -> None:
        """Roll back pending changes."""
        ...
