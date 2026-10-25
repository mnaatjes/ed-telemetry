"""Data and control plane event envelopes for file ingestion and lifecycle auditing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID


class FileKind(StrEnum):
    """Category of ingested telemetry file."""

    JOURNAL = "journal"
    STATUS = "status"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True)
class FileIngestionEvent:
    """
    Data Plane Envelope emitted upon extracting a valid raw byte slice from disk.
    Strictly contains raw byte payload with zero domain parsing.
    """

    event_id: UUID
    timestamp: datetime  # UTC ISO 8601
    file_kind: FileKind
    target_path: Path
    raw_payload: bytes
    start_offset: int
    end_offset: int
    line_number: int | None  # 1-indexed for journals; None for snapshots
    part: int | None  # Journal part sequence (e.g. 1, 2); None for snapshots
    raw_hash: str  # 64-bit BLAKE2b digest string


class WatcherAuditAction(StrEnum):
    """Operational lifecycle and diagnostic transition types."""

    DISCOVERED = "discovered"
    SELECTED = "selected"
    POLL_TICK = "poll_tick"
    FRESHNESS_VERIFIED = "freshness_verified"
    RETRY_BACKOFF = "retry_backoff"
    PART_ROLLOVER = "part_rollover"
    LINE_QUARANTINED = "line_quarantined"
    CASING_COLLISION_DETECTED = "casing_collision_detected"
    EMPTY_CANDIDATE_SET = "empty_candidate_set"
    HINT_ENQUEUED = "hint_enqueued"
    HINT_DISPATCHED = "hint_dispatched"
    HINT_DROPPED = "hint_dropped"
    INVALID_FILE_TYPE = "invalid_file_type"


@dataclass(frozen=True)
class WatcherAuditEvent:
    """
    Control & Observability Plane Envelope emitted on internal state transitions.
    Decoupled from data ingestion payloads.
    """

    timestamp: datetime  # UTC ISO 8601
    action: WatcherAuditAction
    target_path: Path
    detail: str = ""
