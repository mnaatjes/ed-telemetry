"""Content freshness tracking and deduplication using 64-bit BLAKE2b digests."""

from __future__ import annotations

import hashlib


class SnapshotFreshnessTracker:
    """
    Tracks raw content digests per snapshot filename to discard duplicate payloads.
    Utilizes 64-bit BLAKE2b hashing for microsecond-scale execution with zero allocations.
    """

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def compute_hash(self, raw_bytes: bytes) -> str:
        """Compute 64-bit (16 hex character) BLAKE2b digest string."""
        return hashlib.blake2b(raw_bytes, digest_size=8).hexdigest()

    def check_and_update(self, name: str, raw_bytes: bytes) -> tuple[bool, str]:
        """
        Evaluate if raw_bytes represents fresh (unseen) content for target name.
        Returns (is_fresh, current_hash). If fresh, updates internal state.
        """
        current_hash = self.compute_hash(raw_bytes)
        last_hash = self._hashes.get(name)

        if last_hash == current_hash:
            return False, current_hash

        self._hashes[name] = current_hash
        return True, current_hash

    def get_hash(self, name: str) -> str | None:
        """Retrieve last recorded hash for a target file."""
        return self._hashes.get(name)

    def clear(self) -> None:
        """Reset internal hash history."""
        self._hashes.clear()
