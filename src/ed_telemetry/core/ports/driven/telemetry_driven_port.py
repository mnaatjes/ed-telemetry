"""Driven (outbound / secondary) port contracts and boundary DTOs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from ..base import DataTransferObject, DrivenPort


@dataclass(frozen=True, slots=True)
class FileIngestionEventDTO(DataTransferObject):
    """Immutable data plane envelope emitted upon extracting a raw byte slice from disk."""

    event_id: UUID
    timestamp: datetime
    file_kind: str  # "journal", "status", "snapshot"
    target_path: Path
    raw_payload: bytes
    start_offset: int
    end_offset: int
    line_number: int | None
    part: int | None
    raw_hash: str


@dataclass(frozen=True, slots=True)
class WatcherAuditEventDTO(DataTransferObject):
    """Immutable control plane operational event emitted on internal watcher transitions."""

    timestamp: datetime
    action: str
    target_path: Path
    detail: str = ""


@dataclass(frozen=True, slots=True)
class TelemetryPayloadDTO(DataTransferObject):
    """Normalized outbound payload transmitted to discrete egress sinks."""

    topic: str
    timestamp: datetime
    payload_bytes: bytes
    metadata: tuple[tuple[str, str], ...] = ()


IngestionEventHandler = Callable[[FileIngestionEventDTO], None]
AuditEventHandler = Callable[[WatcherAuditEventDTO], None]


@runtime_checkable
class LifecyclePort(DrivenPort, Protocol):
    """Capability protocol for driven workers requiring execution management."""

    def start(self) -> None: ...

    def stop(self) -> None: ...

    @property
    def is_active(self) -> bool: ...


@runtime_checkable
class StreamSourcePort(DrivenPort, Protocol):
    """Capability protocol for continuous inbound event streaming sources."""

    def register_event_handler(self, handler: IngestionEventHandler) -> None: ...

    def register_audit_handler(self, handler: AuditEventHandler) -> None: ...


@runtime_checkable
class DiscreteSinkPort(DrivenPort, Protocol):
    """Capability protocol for discrete, outbound point-in-time transmission sinks."""

    def send(self, payload: TelemetryPayloadDTO) -> None: ...


@runtime_checkable
class WatcherPort(DrivenPort, LifecyclePort, StreamSourcePort, Protocol):
    """Composite driven port contract for inbound telemetry file watchers."""

    @property
    def journal_dir(self) -> Path | None: ...


@runtime_checkable
class EgressPort(DrivenPort, DiscreteSinkPort, Protocol):
    """Driven port contract for transmitting telemetry payloads to external endpoints."""
