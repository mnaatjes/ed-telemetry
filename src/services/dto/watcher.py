"""Data Transfer Objects for watcher telemetry."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WatcherStatusDTO:
    """Immutable status representation of the telemetry watcher adapter."""

    is_active: bool
    journal_dir: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize status fields to primitive dictionary."""
        return {
            "is_active": self.is_active,
            "journal_dir": self.journal_dir,
        }
