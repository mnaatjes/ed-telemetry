"""Domain models and enumerations for OS path discovery."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SupportedPlatform(StrEnum):
    """Supported host operating system execution platforms."""

    WINDOWS = "win32"
    LINUX = "linux"
    UNSUPPORTED = "unsupported"

    @classmethod
    def from_current_platform(cls) -> SupportedPlatform:
        """Detect the supported platform category from sys.platform."""
        if sys.platform == "win32":
            return cls.WINDOWS
        if sys.platform.startswith("linux"):
            return cls.LINUX
        return cls.UNSUPPORTED


@dataclass(frozen=True)
class DiscoveryResult:
    """Immutable result from a successful journal directory resolution."""

    resolved_path: Path
    discovery_source: str
