"""Unit tests for Status and Auxiliary Snapshot Identification (ADR 0007 / SDD-005)."""

import sys
from pathlib import Path

import pytest
from ed_watcher.exceptions import (
    InvalidSnapshotFileTypeError,
    SnapshotCollisionError,
    SnapshotDirectoryAccessError,
    SnapshotRegistrationError,
    UnregisteredSnapshotError,
)
from ed_watcher.snapshots import (
    CANONICAL_AUXILIARY_SNAPSHOTS,
    SnapshotIdentifier,
    SnapshotRegistry,
)


class TestSnapshotRegistry:
    """Test registry catalog and validation gates."""

    def test_canonical_catalog_contains_expected_files(self) -> None:
        reg = SnapshotRegistry()
        assert reg.status_file == "Status.json"
        assert "Market.json" in reg.all_auxiliary()
        assert "Cargo.json" in reg.all_auxiliary()
        assert "NavRoute.json" in reg.all_auxiliary()
        assert len(reg.all_auxiliary()) == len(CANONICAL_AUXILIARY_SNAPSHOTS)

    def test_case_insensitive_canonical_name_lookup(self) -> None:
        reg = SnapshotRegistry()
        assert reg.canonical_name("status.json") == "Status.json"
        assert reg.canonical_name("MARKET.JSON") == "Market.json"
        assert reg.canonical_name("navroute.json") == "NavRoute.json"
        assert reg.canonical_name("unknown.json") is None

    def test_register_custom_snapshot_success(self) -> None:
        reg = SnapshotRegistry()
        reg.register_custom("CustomState.json")
        assert "CustomState.json" in reg.all_auxiliary()
        assert reg.canonical_name("customstate.json") == "CustomState.json"

    def test_register_custom_rejects_path_traversal(self) -> None:
        reg = SnapshotRegistry()
        with pytest.raises(SnapshotRegistrationError, match="path_traversal"):
            reg.register_custom("../alien.json")
        with pytest.raises(SnapshotRegistrationError, match="path_traversal"):
            reg.register_custom("sub/dir.json")
        with pytest.raises(SnapshotRegistrationError, match="path_traversal"):
            reg.register_custom("/etc/passwd.json")

    def test_register_custom_rejects_invalid_extension(self) -> None:
        reg = SnapshotRegistry()
        with pytest.raises(SnapshotRegistrationError, match="invalid_extension"):
            reg.register_custom("CustomState.txt")

    def test_register_custom_rejects_journal_prefix_collision(self) -> None:
        reg = SnapshotRegistry()
        with pytest.raises(SnapshotRegistrationError, match="journal_collision"):
            reg.register_custom("Journal.2026-10-08.json")


class TestSnapshotIdentifier:
    """Test candidate resolution, casing normalization, and error semantics."""

    def test_empty_directory_returns_none_gracefully(self, tmp_path: Path) -> None:
        ident = SnapshotIdentifier(tmp_path)
        assert ident.resolve_status() is None
        assert ident.resolve_auxiliary("Market.json") is None
        assert ident.resolve_all_available() == ()

    def test_directory_access_error_on_missing_dir(self, tmp_path: Path) -> None:
        missing = tmp_path / "non_existent"
        ident = SnapshotIdentifier(missing)
        with pytest.raises(SnapshotDirectoryAccessError) as exc_info:
            ident.resolve_status()
        assert exc_info.value.reason == "does_not_exist"

    def test_resolves_canonical_pascal_case_fast_path(self, tmp_path: Path) -> None:
        status_file = tmp_path / "Status.json"
        market_file = tmp_path / "Market.json"
        status_file.write_text('{"event": "Status"}')
        market_file.write_text('{"event": "Market"}')

        ident = SnapshotIdentifier(tmp_path)

        cand_status = ident.resolve_status()
        assert cand_status is not None
        assert cand_status.canonical_name == "Status.json"
        assert cand_status.resolved_path == status_file
        assert cand_status.is_canonical_casing is True
        assert cand_status.size > 0

        cand_market = ident.resolve_auxiliary("Market.json")
        assert cand_market is not None
        assert cand_market.canonical_name == "Market.json"
        assert cand_market.resolved_path == market_file
        assert cand_market.is_canonical_casing is True

    def test_posix_case_folding_fallback(self, tmp_path: Path) -> None:
        # Create lowercase files on POSIX
        status_lower = tmp_path / "status.json"
        market_lower = tmp_path / "market.json"
        status_lower.write_text('{"event": "Status"}')
        market_lower.write_text('{"event": "Market"}')

        # Enable posix_mode explicitly to test case-folding
        ident = SnapshotIdentifier(tmp_path, posix_mode=True)

        cand_status = ident.resolve_status()
        assert cand_status is not None
        assert cand_status.canonical_name == "Status.json"
        assert cand_status.resolved_path == status_lower
        assert cand_status.is_canonical_casing is False

        cand_market = ident.resolve_auxiliary("Market.json")
        assert cand_market is not None
        assert cand_market.canonical_name == "Market.json"
        assert cand_market.resolved_path == market_lower
        assert cand_market.is_canonical_casing is False

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows NTFS is case-insensitive")
    def test_canonical_pascal_case_priority_on_collision(self, tmp_path: Path) -> None:
        # Both Status.json AND status.json exist on case-sensitive POSIX filesystem
        status_canonical = tmp_path / "Status.json"
        status_lower = tmp_path / "status.json"
        status_canonical.write_text('{"canonical": true}')
        status_lower.write_text('{"lower": true}')

        ident = SnapshotIdentifier(tmp_path, posix_mode=True)
        cand = ident.resolve_status()

        assert cand is not None
        # Canonical PascalCase must be prioritized
        assert cand.resolved_path == status_canonical
        assert cand.is_canonical_casing is True

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Windows NTFS is case-insensitive and cannot create same-name casing collisions"
    )
    def test_ambiguous_casing_collision_raises_error(self, tmp_path: Path) -> None:
        # Multiple non-canonical variations exist without canonical PascalCase
        f1 = tmp_path / "status.json"
        f2 = tmp_path / "STATUS.JSON"
        f1.touch()
        f2.touch()

        ident = SnapshotIdentifier(tmp_path, posix_mode=True)
        with pytest.raises(SnapshotCollisionError) as exc_info:
            ident.resolve_status()
        assert exc_info.value.canonical_name == "Status.json"

    def test_unregistered_snapshot_raises_error(self, tmp_path: Path) -> None:
        ident = SnapshotIdentifier(tmp_path)
        with pytest.raises(UnregisteredSnapshotError) as exc_info:
            ident.resolve_auxiliary("UnregisteredAlienFile.json")
        assert exc_info.value.requested_name == "UnregisteredAlienFile.json"

    def test_invalid_snapshot_file_type_raises_and_quarantines(self, tmp_path: Path) -> None:
        # Create a directory named Status.json
        dir_status = tmp_path / "Status.json"
        dir_status.mkdir()

        ident = SnapshotIdentifier(tmp_path)

        with pytest.raises(InvalidSnapshotFileTypeError) as exc_info:
            ident.resolve_status()
        assert exc_info.value.actual_type == "directory"

        # resolve_all_available() should skip/quarantine without raising
        all_avail = ident.resolve_all_available()
        assert len(all_avail) == 0
