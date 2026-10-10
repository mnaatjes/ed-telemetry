"""Abstract ports for inbound telemetry watchers.

Governed by ADR 0015 and SDD-013.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.ports.base import (
    AuditEventHandler,
    IngestionEventHandler,
    LifecyclePort,
    StreamSourcePort,
)

__all__ = ["WatcherPort", "IngestionEventHandler", "AuditEventHandler"]


@runtime_checkable
class WatcherPort(LifecyclePort, StreamSourcePort, Protocol):
    """Contract for inbound file and telemetry watchers.

    Composes LifecyclePort (worker archetype) and StreamSourcePort (event streaming).
    Lifecycle hooks (start, stop, is_active) are inherited directly from LifecyclePort.
    """
