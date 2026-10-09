"""Canonical catalog and dynamic registration gate for FDev snapshot files."""

from __future__ import annotations

from pathlib import Path

from ed_watcher.exceptions import SnapshotRegistrationError

CANONICAL_STATUS_FILE = "Status.json"

CANONICAL_AUXILIARY_SNAPSHOTS = frozenset(
    {
        "Market.json",
        "Outfitting.json",
        "Shipyard.json",
        "ModulesInfo.json",
        "Cargo.json",
        "Backpack.json",
        "NavRoute.json",
        "ShipLocker.json",
        "FCMaterials.json",
    }
)


class SnapshotRegistry:
    """
    Catalog governing recognized FDev snapshot filenames with validation gates.
    """

    def __init__(self, custom_snapshots: set[str] | None = None) -> None:
        self._auxiliary_snapshots: set[str] = set(CANONICAL_AUXILIARY_SNAPSHOTS)
        if custom_snapshots:
            for item in custom_snapshots:
                self.register_custom(item)

    @property
    def status_file(self) -> str:
        """The canonical status heartbeat filename."""
        return CANONICAL_STATUS_FILE

    def all_auxiliary(self) -> frozenset[str]:
        """Return all registered auxiliary snapshot names."""
        return frozenset(self._auxiliary_snapshots)

    def all_registered(self) -> frozenset[str]:
        """Return all registered filenames (status + auxiliary)."""
        return frozenset(self._auxiliary_snapshots | {CANONICAL_STATUS_FILE})

    def is_registered(self, filename: str) -> bool:
        """Check if filename matches any registered snapshot (case-insensitive)."""
        return self.canonical_name(filename) is not None

    def canonical_name(self, query: str) -> str | None:
        """
        Resolve a query string to its canonical PascalCase name if registered.
        Matches case-insensitively.
        """
        query_lower = query.lower()
        if query_lower == CANONICAL_STATUS_FILE.lower():
            return CANONICAL_STATUS_FILE
        for name in self._auxiliary_snapshots:
            if name.lower() == query_lower:
                return name
        return None

    def register_custom(self, filename: str) -> None:
        """
        Register a custom auxiliary snapshot filename.
        Enforces security invariants:
        1. Pure Basename (no directory separators or traversal).
        2. Must end in .json.
        3. Cannot start with 'Journal'.
        """
        # 1. Pure Basename Invariant (Directory Traversal Defense)
        p = Path(filename)
        if p.name != filename or "/" in filename or "\\" in filename or ".." in filename:
            raise SnapshotRegistrationError(
                filename,
                reason="path_traversal (must be a pure basename without directory separators)",
            )

        # 2. Extension Invariant
        if not filename.endswith(".json"):
            raise SnapshotRegistrationError(
                filename,
                reason="invalid_extension (snapshot files must have a .json extension)",
            )

        # 3. Stream Separation Invariant (Journal Collision Defense)
        if filename.startswith("Journal"):
            raise SnapshotRegistrationError(
                filename,
                reason="journal_collision (cannot register filenames with 'Journal' prefix)",
            )

        self._auxiliary_snapshots.add(filename)
