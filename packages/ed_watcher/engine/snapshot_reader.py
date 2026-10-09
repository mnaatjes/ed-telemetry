"""Atomic snapshot reading with 20ms debouncing, structural boundary guards, and backoff retries."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ed_watcher.engine.envelopes import (
    FileIngestionEvent,
    FileKind,
    WatcherAuditAction,
    WatcherAuditEvent,
)
from ed_watcher.engine.freshness import SnapshotFreshnessTracker

DEFAULT_RETRY_BACKOFFS: Sequence[float] = (0.02, 0.04, 0.08)  # 20ms, 40ms, 80ms


class SnapshotReader:
    """
    Safely whole-reads JSON state snapshots without JSON parsing.
    Guards against in-progress truncations and duplicate emissions.
    """

    def __init__(
        self,
        freshness_tracker: SnapshotFreshnessTracker | None = None,
        retry_backoffs: Sequence[float] = DEFAULT_RETRY_BACKOFFS,
    ) -> None:
        self.freshness_tracker = freshness_tracker if freshness_tracker is not None else SnapshotFreshnessTracker()
        self.retry_backoffs = tuple(retry_backoffs)

    def read_snapshot(
        self,
        target_path: Path,
        file_kind: FileKind,
    ) -> tuple[FileIngestionEvent | None, list[WatcherAuditEvent]]:
        """
        Whole-read target snapshot with structural delimiter check and backoff retries.
        Returns FileIngestionEvent if fresh, None if duplicate or absent/invalid, plus audit logs.
        """
        audit_events: list[WatcherAuditEvent] = []

        if not target_path.exists() or not target_path.is_file():
            return None, audit_events

        raw_bytes: bytes = b""
        success = False

        # Attempt atomic read with exponential backoff on truncation race
        for attempt, delay in enumerate((0.0, *self.retry_backoffs)):
            if delay > 0.0:
                time.sleep(delay)

            try:
                raw_bytes = target_path.read_bytes().strip()
            except OSError:
                continue

            # Structural JSON Boundary Guard (no JSON parsing):
            # Must be non-empty and start with '{' and end with '}'
            if len(raw_bytes) > 0 and raw_bytes.startswith(b"{") and raw_bytes.endswith(b"}"):
                success = True
                break

            if attempt > 0:
                audit_events.append(
                    WatcherAuditEvent(
                        timestamp=datetime.now(UTC),
                        action=WatcherAuditAction.RETRY_BACKOFF,
                        target_path=target_path,
                        detail=(
                            f"Incomplete structural boundary on attempt {attempt}; retrying after {delay * 1000:.0f}ms"
                        ),
                    )
                )

        if not success or not raw_bytes:
            return None, audit_events

        # Check BLAKE2b Freshness Gate
        canonical_name = target_path.name
        is_fresh, raw_hash = self.freshness_tracker.check_and_update(canonical_name, raw_bytes)

        if not is_fresh:
            # Duplicate payload: discard silently
            return None, audit_events

        # Emit Data Plane Event
        event = FileIngestionEvent(
            event_id=uuid4(),
            timestamp=datetime.now(UTC),
            file_kind=file_kind,
            target_path=target_path,
            raw_payload=raw_bytes,
            start_offset=0,
            end_offset=len(raw_bytes),
            line_number=None,
            part=None,
            raw_hash=raw_hash,
        )

        return event, audit_events
