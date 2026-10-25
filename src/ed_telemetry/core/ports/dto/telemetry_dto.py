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


@dataclass(frozen=True, slots=True)
class JournalPathDTO(DataTransferObject):
    """Result of journal directory discovery."""

    resolved_path: str
    platform: str
    discovery_source: str


@dataclass(frozen=True, slots=True)
class JournalCandidateDTO(DataTransferObject):
    """Metadata for an identified journal candidate file."""

    filename: str
    path: str
    timestamp: datetime
    part: int
    mtime: float
    is_standard_format: bool


@dataclass(frozen=True, slots=True)
class JournalFileListDTO(DataTransferObject):
    """Chronologically sorted journal candidate files in target directory."""

    journal_dir: str
    candidates: tuple[JournalCandidateDTO, ...]
    active_journal: str | None


@dataclass(frozen=True, slots=True)
class GameStatusSnapshotDTO(DataTransferObject):
    """Extracted payload and metadata for Status.json."""

    exists: bool
    target_path: str | None
    timestamp: datetime | None
    raw_payload: bytes
    raw_hash: str | None


@dataclass(frozen=True, slots=True)
class AuxiliarySnapshotDTO(DataTransferObject):
    """Extracted payload and metadata for an auxiliary snapshot file."""

    target_name: str
    exists: bool
    target_path: str | None
    timestamp: datetime | None
    raw_payload: bytes
    raw_hash: str | None


@dataclass(frozen=True, slots=True)
class HintSubmissionDTO(DataTransferObject):
    """Result of submitting an operational hint to the watcher reactor queue."""

    action: str
    target_name: str | None
    accepted: bool
    detail: str


@dataclass(frozen=True, slots=True)
class TelemetryBatchDTO(DataTransferObject):
    """Batch of telemetry payloads polled from an outbound buffered queue."""

    events: tuple[TelemetryPayloadDTO, ...]
    remaining_count: int
    dropped_count: int
