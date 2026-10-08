"""Exception hierarchy for journal candidate selection and watcher infrastructure."""

from __future__ import annotations

from pathlib import Path

from ed_watcher.discovery.exceptions import WatcherError


class JournalDirectoryAccessError(WatcherError):
    """
    Raised when the target journal directory cannot be accessed,
    does not exist, is not a directory, or has insufficient read permissions.

    Attributes:
        target_path: The invalid or inaccessible directory Path.
        reason: Diagnostic reason for failure ('does_not_exist', 'not_a_directory', 'permission_denied').
    """

    def __init__(self, target_path: Path, reason: str) -> None:
        self.target_path = target_path
        self.reason = reason
        super().__init__(
            f"Failed to access journal directory '{target_path}' ({reason}). "
            "Verify the path exists, is a valid directory, and grants read permissions."
        )
