"""Driven (outbound / secondary) port contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from ..base import DrivenPort
from ..dto.telemetry_dto import (
    AuxiliarySnapshotDTO,
    FileIngestionEventDTO,
    GameStatusSnapshotDTO,
    HintSubmissionDTO,
    JournalFileListDTO,
    JournalPathDTO,
    TelemetryPayloadDTO,
    WatcherAuditEventDTO,
)

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
class WatcherPort(LifecyclePort, StreamSourcePort, DrivenPort, Protocol):
    """Composite driven port contract for inbound telemetry file watchers."""

    @property
    def journal_dir(self) -> str | None: ...

    def discover_path(self, override_path: str | None = None) -> JournalPathDTO: ...

    def list_journals(self) -> JournalFileListDTO: ...

    def read_status_snapshot(self) -> GameStatusSnapshotDTO: ...

    def read_auxiliary_snapshot(self, name: str) -> AuxiliarySnapshotDTO: ...

    def submit_ingest_hint(self, action: str, target_name: str | None = None) -> HintSubmissionDTO: ...


@runtime_checkable
class EgressPort(DiscreteSinkPort, DrivenPort, Protocol):
    """Driven port contract for transmitting telemetry payloads to external endpoints."""
