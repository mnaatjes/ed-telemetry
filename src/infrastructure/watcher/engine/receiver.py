"""Inbound control plane port and command queue contracts for the watcher reactor."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class WatcherHintAction(StrEnum):
    """Actions requested by external components across the feedback boundary."""

    HINT_SNAPSHOT = "hint_snapshot"  # Request immediate read of specific snapshot
    HINT_ROLLOVER = "hint_rollover"  # Request immediate evaluation for next journal part
    HINT_DIRECTORY_SCAN = "hint_scan"  # Request immediate directory sweep


@dataclass(frozen=True)
class WatcherIngestCommand:
    """
    Agnostic filesystem hint received across the boundary.
    Contains zero game schema logic.
    """

    action: WatcherHintAction
    target_name: str | None = None  # e.g., "Market.json", "NavRoute.json", or None
    priority: bool = False  # If True, bypasses drop policy during queue congestion


@dataclass(frozen=True)
class ReactorQueueMetrics:
    """Read-only operational telemetry on the inbound command queue for logging and debugging."""

    current_depth: int
    capacity: int
    high_water_mark: int
    total_enqueued: int
    total_processed: int
    total_dropped: int


class WatcherIngestReceiver(Protocol):
    """Inbound boundary protocol implemented by the reactive reactor."""

    def submit_hint(self, command: WatcherIngestCommand) -> bool:
        """
        Enqueues an operational hint and signals the reactor loop to wake immediately.
        Returns True if enqueued, False if dropped due to queue saturation.
        """
        ...

    def get_queue_metrics(self) -> ReactorQueueMetrics:
        """Returns observable telemetry on queue depth, saturation, and drop counters."""
        ...
