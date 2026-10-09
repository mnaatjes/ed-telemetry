"""Isolated per-file streaming state machine for journal handles."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from infrastructure.watcher.selector import StreamPosition


@dataclass
class JournalStreamContext:
    """
    Isolated, per-file streaming state machine.
    Strictly instantiated per physical journal file; never shared or global.
    """

    target_path: Path
    handle: BinaryIO
    part: int
    last_valid_offset: int = 0
    current_line_number: int = 1
    fragment_accumulator: bytearray = field(default_factory=bytearray)
    fragment_first_seen: float | None = None
    is_retired: bool = False

    def close(self) -> None:
        """Finalize and release handle."""
        if not self.handle.closed:
            self.handle.close()
        self.is_retired = True

    @classmethod
    def open(
        cls,
        path: Path,
        part: int,
        position: StreamPosition = StreamPosition.HEAD,
    ) -> JournalStreamContext:
        """
        Open physical file in read-only binary mode and bind initial monotonic offset.
        Applies StreamPosition policy at handle inception.
        """
        handle = path.open("rb")
        initial_offset = 0

        if position == StreamPosition.TAIL:
            try:
                initial_offset = path.stat().st_size
            except OSError:
                initial_offset = 0
            handle.seek(initial_offset, os.SEEK_SET)
        else:
            handle.seek(0, os.SEEK_SET)

        return cls(
            target_path=path,
            handle=handle,
            part=part,
            last_valid_offset=initial_offset,
            current_line_number=1,
            fragment_accumulator=bytearray(),
            fragment_first_seen=None,
            is_retired=False,
        )
