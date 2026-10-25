"""In-memory diagnostic log ring buffer adapter."""

from __future__ import annotations

import collections
import datetime
import logging
import threading

from ed_telemetry.core.ports.driven.telemetry_driven_port import DiagnosticLogPort
from ed_telemetry.core.ports.dto.telemetry_dto import (
    DiagnosticLogRecordDTO,
    DiagnosticLogSnapshotDTO,
)

_LOG_LEVEL_WEIGHTS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class DiagnosticLogBuffer(logging.Handler, DiagnosticLogPort):
    """Thread-safe ring buffer capturing log records for runtime diagnostics."""

    def __init__(self, capacity: int = 1000) -> None:
        super().__init__()
        self._capacity = max(1, capacity)
        self._buffer: collections.deque[DiagnosticLogRecordDTO] = collections.deque(maxlen=self._capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Capture and normalize log records into immutable DTOs."""
        try:
            timestamp = datetime.datetime.fromtimestamp(record.created, tz=datetime.UTC)
            message = self.format(record) if self.formatter else record.getMessage()
            entry = DiagnosticLogRecordDTO(
                timestamp=timestamp,
                level=record.levelname,
                logger_name=record.name,
                message=message,
            )
            with self._lock:
                self._buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_recent_logs(
        self,
        min_level: str | None = None,
        limit: int = 100,
    ) -> DiagnosticLogSnapshotDTO:
        """Retrieve a filtered snapshot of buffered diagnostic logs."""
        safe_limit = max(1, limit)
        threshold = 0
        if min_level:
            threshold = _LOG_LEVEL_WEIGHTS.get(min_level.upper(), 0)

        with self._lock:
            records = list(self._buffer)

        if threshold > 0:
            records = [r for r in records if _LOG_LEVEL_WEIGHTS.get(r.level.upper(), 0) >= threshold]

        # Slice the most recent entries up to safe_limit
        selected = tuple(records[-safe_limit:])
        return DiagnosticLogSnapshotDTO(
            records=selected,
            total_retained=len(selected),
        )

    def clear(self) -> None:
        """Empty all records in buffer."""
        with self._lock:
            self._buffer.clear()
