"""Exception hierarchy for journal candidate selection and snapshot infrastructure."""

from __future__ import annotations

from pathlib import Path

from infrastructure.watcher.discovery.exceptions import WatcherError


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


class SnapshotIdentificationError(WatcherError):
    """Base exception for all status and auxiliary snapshot identification failures."""


class SnapshotDirectoryAccessError(SnapshotIdentificationError):
    """Raised when the snapshot directory cannot be accessed or inspected."""

    def __init__(self, target_path: Path, reason: str) -> None:
        self.target_path = target_path
        self.reason = reason
        super().__init__(
            f"Failed to access snapshot directory '{target_path}' ({reason}). "
            "Verify the path exists, is a valid directory, and grants read permissions."
        )


class UnregisteredSnapshotError(SnapshotIdentificationError):
    """Raised when resolution is attempted for a filename not in the registered catalog."""

    def __init__(self, requested_name: str, available_registry: frozenset[str]) -> None:
        self.requested_name = requested_name
        self.available_registry = available_registry
        super().__init__(
            f"Cannot resolve unregistered snapshot '{requested_name}'. "
            f"Registered catalog: {sorted(available_registry)}."
        )


class SnapshotCollisionError(SnapshotIdentificationError):
    """Raised when ambiguous multiple non-canonical casing variants exist without a canonical PascalCase file."""

    def __init__(self, canonical_name: str, colliding_paths: tuple[Path, ...]) -> None:
        self.canonical_name = canonical_name
        self.colliding_paths = colliding_paths
        super().__init__(
            f"Ambiguous casing collision for snapshot '{canonical_name}'. "
            f"Multiple conflicting files found without canonical PascalCase variant: {colliding_paths}."
        )


class SnapshotRegistrationError(SnapshotIdentificationError):
    """Raised when an invalid custom snapshot filename is supplied to the registry."""

    def __init__(self, invalid_name: str, reason: str) -> None:
        self.invalid_name = invalid_name
        self.reason = reason
        super().__init__(f"Invalid snapshot registration '{invalid_name}': {reason}.")


class InvalidSnapshotFileTypeError(SnapshotIdentificationError):
    """Raised when an entity matching a snapshot name exists on disk but is not a regular file."""

    def __init__(self, target_path: Path, actual_type: str) -> None:
        self.target_path = target_path
        self.actual_type = actual_type
        super().__init__(f"Snapshot target '{target_path}' is not a regular file (detected: {actual_type}).")
