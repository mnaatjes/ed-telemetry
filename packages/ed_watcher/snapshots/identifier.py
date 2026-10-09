"""Status and auxiliary snapshot candidate identifier with casing normalization."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ed_watcher.exceptions import (
    InvalidSnapshotFileTypeError,
    SnapshotCollisionError,
    SnapshotDirectoryAccessError,
    UnregisteredSnapshotError,
)
from ed_watcher.snapshots.models import SnapshotCandidate
from ed_watcher.snapshots.registry import (
    CANONICAL_STATUS_FILE,
    SnapshotRegistry,
)


class SnapshotIdentifier:
    """
    Coordinates filesystem inspection and candidate resolution for status and auxiliary snapshots.
    """

    def __init__(
        self,
        journal_dir: Path,
        registry: SnapshotRegistry | None = None,
        posix_mode: bool | None = None,
    ) -> None:
        self.journal_dir = journal_dir
        self.registry = registry if registry is not None else SnapshotRegistry()
        # On POSIX (Linux/macOS), filesystems are typically case-sensitive
        self.posix_mode = posix_mode if posix_mode is not None else (sys.platform != "win32")

    def _validate_directory(self) -> None:
        """Validate target directory exists, is a directory, and is readable."""
        if not self.journal_dir.exists():
            raise SnapshotDirectoryAccessError(self.journal_dir, reason="does_not_exist")
        if not self.journal_dir.is_dir():
            raise SnapshotDirectoryAccessError(self.journal_dir, reason="not_a_directory")

    def _inspect_node(self, path: Path, canonical_name: str, is_canonical_casing: bool) -> SnapshotCandidate:
        """Inspect a located node and construct SnapshotCandidate. Enforces regular file check."""
        if not path.is_file():
            # Directory, FIFO, or socket collision
            actual_type = "directory" if path.is_dir() else "special_node"
            raise InvalidSnapshotFileTypeError(path, actual_type=actual_type)

        try:
            stat_res = path.stat()
            mtime = stat_res.st_mtime
            size = stat_res.st_size
        except OSError:
            mtime = 0.0
            size = 0

        return SnapshotCandidate(
            canonical_name=canonical_name,
            resolved_path=path,
            exists=True,
            is_canonical_casing=is_canonical_casing,
            mtime=mtime,
            size=size,
        )

    def _resolve_target(self, canonical_name: str) -> SnapshotCandidate | None:
        """
        Resolve a single target using Fast-Path then POSIX case-folding fallback.
        Enforces Canonical PascalCase Priority on collisions.
        """
        self._validate_directory()

        fast_path = self.journal_dir / canonical_name
        if fast_path.exists():
            return self._inspect_node(fast_path, canonical_name, is_canonical_casing=True)

        # On non-POSIX (Windows), if fast_path.exists() is False, the file does not exist
        if not self.posix_mode:
            return None

        # POSIX Case-Folding Normalization Fallback
        target_lower = canonical_name.lower()
        matching_paths: list[Path] = []

        try:
            with os.scandir(self.journal_dir) as entries:
                for entry in entries:
                    if entry.name.lower() == target_lower:
                        matching_paths.append(Path(entry.path))
        except PermissionError as err:
            raise SnapshotDirectoryAccessError(self.journal_dir, reason="permission_denied") from err
        except OSError as err:
            raise SnapshotDirectoryAccessError(self.journal_dir, reason="os_error") from err

        if not matching_paths:
            return None

        if len(matching_paths) == 1:
            return self._inspect_node(matching_paths[0], canonical_name, is_canonical_casing=False)

        # Casing Collision Ambiguity (e.g., status.json AND STATUS.json both exist)
        # Check if one is canonical PascalCase (though fast_path would normally catch it)
        for p in matching_paths:
            if p.name == canonical_name:
                return self._inspect_node(p, canonical_name, is_canonical_casing=True)

        raise SnapshotCollisionError(canonical_name, tuple(matching_paths))

    def resolve_status(self) -> SnapshotCandidate | None:
        """
        Resolve Status.json candidate.
        Returns None if file is absent (e.g. before initial game startup).
        """
        return self._resolve_target(CANONICAL_STATUS_FILE)

    def resolve_auxiliary(self, name: str) -> SnapshotCandidate | None:
        """
        Resolve an auxiliary snapshot candidate by name.
        Raises UnregisteredSnapshotError if name is not in the registry.
        Returns None if file is absent on disk.
        """
        canonical = self.registry.canonical_name(name)
        if canonical is None or canonical == CANONICAL_STATUS_FILE:
            if canonical == CANONICAL_STATUS_FILE:
                return self.resolve_status()
            raise UnregisteredSnapshotError(name, self.registry.all_auxiliary())

        return self._resolve_target(canonical)

    def resolve_all_available(self) -> Sequence[SnapshotCandidate]:
        """
        Inspect directory and return candidates for all currently instantiated registered snapshots.
        Gracefully ignores missing files or quarantined invalid node types.
        """
        self._validate_directory()
        candidates: list[SnapshotCandidate] = []

        for name in self.registry.all_registered():
            try:
                candidate = self._resolve_target(name)
                if candidate is not None:
                    candidates.append(candidate)
            except (InvalidSnapshotFileTypeError, SnapshotCollisionError):
                # Quarantined target: do not crash full enumeration
                continue

        return tuple(candidates)
