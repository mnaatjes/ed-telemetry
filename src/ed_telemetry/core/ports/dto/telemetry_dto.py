"""Immutable boundary Data Transfer Objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..base import DataTransferObject


@dataclass(frozen=True, slots=True)
class WatcherStatusDTO(DataTransferObject):
    """Immutable status snapshot of the telemetry watcher system."""

    is_active: bool
    active_journal: str | None
    monitored_directory: str | None


@dataclass(frozen=True, slots=True)
class StartMonitoringDTO(DataTransferObject):
    """Command payload instructing use case to start telemetry monitoring."""

    journal_dir: str | None = None
    poll_interval: float | None = None


@dataclass(frozen=True, slots=True)
class SnapshotSyncResultDTO(DataTransferObject):
    """Summary of point-in-time snapshot synchronization."""

    files_inspected: int
    payloads_emitted: int
    active_journal_file: str | None


@dataclass(frozen=True, slots=True)
class FileIngestionEventDTO(DataTransferObject):
    """Immutable data plane envelope emitted upon extracting a raw byte slice from disk."""

    event_id: UUID
    timestamp: datetime
    file_kind: str  # "journal", "status", "snapshot"
    target_path: str
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
    target_path: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class TelemetryPayloadDTO(DataTransferObject):
    """Normalized outbound payload transmitted to discrete egress sinks."""

    topic: str
    timestamp: datetime
    payload_bytes: bytes
    metadata: tuple[tuple[str, str], ...] = ()
