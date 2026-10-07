"""Exception hierarchy for OS path discovery and watcher infrastructure."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


class WatcherError(Exception):
    """Base infrastructure exception for all ed_watcher failures."""


class PathDiscoveryError(WatcherError):
    """Base exception for all path discovery failures."""


class UnsupportedPlatformError(PathDiscoveryError):
    """
    Raised when the runtime encounters an operating system without an automated strategy.

    Attributes:
        platform_name: The raw sys.platform string that was rejected.
    """

    def __init__(self, platform_name: str) -> None:
        self.platform_name = platform_name
        super().__init__(
            f"Unsupported operating system platform: '{platform_name}'. "
            "Automated path discovery is only supported on Windows (win32) and Linux. "
            "Supply an explicit path parameter or set the ED_JOURNAL_DIR environment variable."
        )


class InvalidPathOverrideError(PathDiscoveryError):
    """
    Raised when an explicit override path (parameter or environment variable)
    does not exist or is not a readable directory.

    Attributes:
        target_path: The invalid Path provided.
        source: The origin of the override ('parameter' or 'environment').
        reason: Diagnostic reason for failure ('does_not_exist', 'not_a_directory', 'permission_denied').
    """

    def __init__(self, target_path: Path, source: str, reason: str) -> None:
        self.target_path = target_path
        self.source = source
        self.reason = reason
        super().__init__(
            f"Invalid journal directory override from {source}: '{target_path}' ({reason}). "
            "Verify the path exists, is a directory, and has read permissions."
        )


class JournalPathNotFoundError(PathDiscoveryError):
    """
    Raised when automated platform strategies exhaust all candidate locations
    without locating a valid Elite Dangerous journal directory.

    Attributes:
        inspected_paths: The ordered sequence of candidate paths evaluated.
        platform_name: The active platform strategy that was executed.
    """

    def __init__(self, inspected_paths: Sequence[Path], platform_name: str) -> None:
        self.inspected_paths = tuple(inspected_paths)
        self.platform_name = platform_name
        formatted_paths = "\n  - ".join(str(p) for p in self.inspected_paths) or "None"
        super().__init__(
            f"Failed to discover Elite Dangerous journal directory on {platform_name}.\n"
            f"Inspected candidate locations:\n  - {formatted_paths}\n\n"
            "Remediation: Launch Elite Dangerous at least once to initialize save files, "
            "or provide an explicit path parameter / ED_JOURNAL_DIR."
        )
