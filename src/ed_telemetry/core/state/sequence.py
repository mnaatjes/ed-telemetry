"""Thread-safe atomic monotonic state sequence tracker."""

from __future__ import annotations

import itertools
import threading


class StateSequenceTracker:
    """
    Monotonically increasing 64-bit sequence counter for telemetry state updates.
    Increments whenever a journal line is appended or a snapshot file is modified.
    """

    def __init__(self, initial_value: int = 1) -> None:
        self._counter = itertools.count(start=initial_value)
        self._lock = threading.Lock()
        self._current_value = initial_value

    def next_sequence(self) -> int:
        """Increment and return the next atomic sequence number."""
        with self._lock:
            val = next(self._counter)
            self._current_value = val
            return val

    @property
    def current_sequence(self) -> int:
        """Return the current sequence number without incrementing."""
        with self._lock:
            return self._current_value
