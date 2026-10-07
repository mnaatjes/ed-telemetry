"""Protocol interface for platform-specific path discovery strategies."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class PathDiscoveryStrategy(Protocol):
    """Strategy interface for finding candidate journal directories on a host OS."""

    @property
    def platform_name(self) -> str:
        """The platform identifier associated with this strategy."""
        ...

    def find_candidates(self) -> Sequence[Path]:
        """
        Enumerate candidate directory paths in prioritized order.

        Returns:
            Sequence of candidate Paths to inspect.
        """
        ...
