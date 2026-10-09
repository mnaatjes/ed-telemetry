"""Monotonic journal stream tailer with newline verification and quarantine circuit breaker."""

from __future__ import annotations

import hashlib
import os
import time
from datetime import UTC, datetime
from uuid import uuid4

from infrastructure.watcher.engine.envelopes import (
    FileIngestionEvent,
    FileKind,
    WatcherAuditAction,
    WatcherAuditEvent,
)
from infrastructure.watcher.engine.stream_context import JournalStreamContext

DEFAULT_READ_BUFFER_SIZE = 64 * 1024  # 64 KB burst buffer
FRAGMENT_STAGNANT_TIMEOUT = 5.0  # 5.0 seconds
FRAGMENT_BUFFER_CEILING = 5 * 1024 * 1024  # 5 MB ceiling


class JournalTailer:
    """
    Reads delta slices from an active JournalStreamContext.
    Enforces Monotonic Forward Seek Invariant (os.SEEK_SET) and fragment circuit breaker.
    """

    def __init__(
        self,
        buffer_size: int = DEFAULT_READ_BUFFER_SIZE,
        stagnant_timeout: float = FRAGMENT_STAGNANT_TIMEOUT,
        buffer_ceiling: int = FRAGMENT_BUFFER_CEILING,
    ) -> None:
        self.buffer_size = buffer_size
        self.stagnant_timeout = stagnant_timeout
        self.buffer_ceiling = buffer_ceiling

    def step(
        self,
        context: JournalStreamContext,
    ) -> tuple[list[FileIngestionEvent], list[WatcherAuditEvent]]:
        """
        Execute one read cycle on the context.
        Returns newly emitted FileIngestionEvents and any control-plane WatcherAuditEvents.
        """
        if context.is_retired or context.handle.closed:
            return [], []

        data_events: list[FileIngestionEvent] = []
        audit_events: list[WatcherAuditEvent] = []
        now = time.time()

        # 1. Monotonic Forward Seek to uncommitted end of accumulated fragment
        read_position = context.last_valid_offset + len(context.fragment_accumulator)
        context.handle.seek(read_position, os.SEEK_SET)
        chunk = context.handle.read(self.buffer_size)

        if chunk:
            context.fragment_accumulator.extend(chunk)
            if context.fragment_first_seen is None:
                context.fragment_first_seen = now

        # If accumulator is empty, nothing to process
        if not context.fragment_accumulator:
            return data_events, audit_events

        # 2. Check for complete lines terminating in b'\n'
        if b"\n" in context.fragment_accumulator:
            # We have at least one complete line
            last_newline_idx = context.fragment_accumulator.rfind(b"\n")
            complete_bytes = bytes(context.fragment_accumulator[: last_newline_idx + 1])
            remaining_fragment = bytearray(context.fragment_accumulator[last_newline_idx + 1 :])

            # Split into individual lines
            current_start_offset = context.last_valid_offset
            for line in complete_bytes.splitlines(keepends=True):
                line_len = len(line)
                line_end_offset = current_start_offset + line_len
                line_hash = hashlib.blake2b(line, digest_size=8).hexdigest()

                data_events.append(
                    FileIngestionEvent(
                        event_id=uuid4(),
                        timestamp=datetime.now(UTC),
                        file_kind=FileKind.JOURNAL,
                        target_path=context.target_path,
                        raw_payload=line,
                        start_offset=current_start_offset,
                        end_offset=line_end_offset,
                        line_number=context.current_line_number,
                        part=context.part,
                        raw_hash=line_hash,
                    )
                )

                current_start_offset = line_end_offset
                context.current_line_number += 1

            # Advance context state
            context.last_valid_offset = current_start_offset
            context.fragment_accumulator = remaining_fragment
            context.fragment_first_seen = now if remaining_fragment else None

            # Reposition handle back to the new valid offset for clean next read
            context.handle.seek(context.last_valid_offset, os.SEEK_SET)

        else:
            # Accumulator has bytes, but NO newline (incomplete line fragment)
            stagnant_duration = (now - context.fragment_first_seen) if context.fragment_first_seen else 0.0
            acc_len = len(context.fragment_accumulator)

            if stagnant_duration >= self.stagnant_timeout or acc_len >= self.buffer_ceiling:
                # 3. Trip Quarantine Circuit Breaker
                reason = "stagnant_timeout" if stagnant_duration >= self.stagnant_timeout else "buffer_ceiling"
                audit_events.append(
                    WatcherAuditEvent(
                        timestamp=datetime.now(UTC),
                        action=WatcherAuditAction.LINE_QUARANTINED,
                        target_path=context.target_path,
                        detail=(
                            f"Orphaned line fragment quarantined ({reason}): "
                            f"{acc_len} bytes held for {stagnant_duration:.2f}s"
                        ),
                    )
                )

                # Skip past orphaned bytes to current EOF
                try:
                    new_eof = context.target_path.stat().st_size
                except OSError:
                    new_eof = context.last_valid_offset + acc_len

                context.last_valid_offset = max(new_eof, context.last_valid_offset + acc_len)
                context.fragment_accumulator.clear()
                context.fragment_first_seen = None
                context.handle.seek(context.last_valid_offset, os.SEEK_SET)
            else:
                # Not timed out yet: rewind file pointer to last valid offset to await next disk flush
                context.handle.seek(context.last_valid_offset, os.SEEK_SET)

        return data_events, audit_events
