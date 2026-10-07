"""Unit test suite for ed_watcher OS path discovery subsystem."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ed_watcher.discovery import (
    DiscoveryResult,
    InvalidPathOverrideError,
    JournalPathNotFoundError,
    PathDiscoverer,
    PathDiscoveryError,
    PathDiscoveryStrategy,
    SupportedPlatform,
    UnsupportedPlatformError,
    WatcherError,
)
from ed_watcher.discovery.strategies.linux import (
    PROTON_REL_PFX,
    LinuxProtonPathStrategy,
)
from ed_watcher.discovery.strategies.windows import (
    SUBDIR_REL_PATH,
    WindowsPathStrategy,
)


class TestDiscoveryModelsAndExceptions:
    """Tests for discovery data structures, enums, and exception hierarchy."""

    def test_supported_platform_detection(self) -> None:
        with patch("sys.platform", "win32"):
            assert SupportedPlatform.from_current_platform() == SupportedPlatform.WINDOWS

        with patch("sys.platform", "linux"):
            assert SupportedPlatform.from_current_platform() == SupportedPlatform.LINUX

        with patch("sys.platform", "linux2"):
            assert SupportedPlatform.from_current_platform() == SupportedPlatform.LINUX

        with patch("sys.platform", "darwin"):
            assert SupportedPlatform.from_current_platform() == SupportedPlatform.UNSUPPORTED

    def test_unsupported_platform_error_attributes(self) -> None:
        err = UnsupportedPlatformError(platform_name="darwin")
        assert err.platform_name == "darwin"
        assert "darwin" in str(err)
        assert isinstance(err, PathDiscoveryError)
        assert isinstance(err, WatcherError)

    def test_invalid_path_override_error_attributes(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "nonexistent"
        err = InvalidPathOverrideError(
            target_path=missing_path,
            source="parameter",
            reason="does_not_exist",
        )
        assert err.target_path == missing_path
        assert err.source == "parameter"
        assert err.reason == "does_not_exist"
        assert "parameter" in str(err)
        assert isinstance(err, PathDiscoveryError)

    def test_journal_path_not_found_error_attributes(self, tmp_path: Path) -> None:
        candidates = [tmp_path / "cand1", tmp_path / "cand2"]
        err = JournalPathNotFoundError(
            inspected_paths=candidates,
            platform_name="Test Platform",
        )
        assert err.inspected_paths == tuple(candidates)
        assert err.platform_name == "Test Platform"
        assert "cand1" in str(err)
        assert "Test Platform" in str(err)
        assert isinstance(err, PathDiscoveryError)

    def test_discovery_result_immutability(self, tmp_path: Path) -> None:
        from dataclasses import FrozenInstanceError

        res = DiscoveryResult(resolved_path=tmp_path, discovery_source="test_source")
        assert res.resolved_path == tmp_path
        assert res.discovery_source == "test_source"
        with pytest.raises(FrozenInstanceError):
            res.resolved_path = tmp_path / "other"  # type: ignore[misc]


class TestExplicitOverrides:
    """Tests for parameter and environment variable override precedence and validation."""

    def test_parameter_override_happy_path(self, tmp_path: Path) -> None:
        target_dir = tmp_path / "custom_journal"
        target_dir.mkdir()

        discoverer = PathDiscoverer(platform_type=SupportedPlatform.LINUX)
        result = discoverer.discover_journal_directory(override_path=target_dir)

        assert result.resolved_path == target_dir.resolve()
        assert result.discovery_source == "parameter_override"

    def test_parameter_override_nonexistent_raises(self, tmp_path: Path) -> None:
        target_dir = tmp_path / "does_not_exist"
        discoverer = PathDiscoverer(platform_type=SupportedPlatform.LINUX)

        with pytest.raises(InvalidPathOverrideError) as exc_info:
            discoverer.discover_journal_directory(override_path=target_dir)

        assert exc_info.value.reason == "does_not_exist"
        assert exc_info.value.source == "parameter"

    def test_parameter_override_file_not_dir_raises(self, tmp_path: Path) -> None:
        target_file = tmp_path / "not_a_dir.txt"
        target_file.write_text("hello")
        discoverer = PathDiscoverer(platform_type=SupportedPlatform.LINUX)

        with pytest.raises(InvalidPathOverrideError) as exc_info:
            discoverer.discover_journal_directory(override_path=target_file)

        assert exc_info.value.reason == "not_a_directory"
        assert exc_info.value.source == "parameter"

    def test_environment_override_happy_path(self, tmp_path: Path) -> None:
        target_dir = tmp_path / "env_journal"
        target_dir.mkdir()

        discoverer = PathDiscoverer(platform_type=SupportedPlatform.LINUX)
        with patch.dict(os.environ, {"ED_JOURNAL_DIR": str(target_dir)}):
            result = discoverer.discover_journal_directory()

        assert result.resolved_path == target_dir.resolve()
        assert result.discovery_source == "env_override"

    def test_parameter_override_takes_precedence_over_env(self, tmp_path: Path) -> None:
        param_dir = tmp_path / "param_dir"
        param_dir.mkdir()
        env_dir = tmp_path / "env_dir"
        env_dir.mkdir()

        discoverer = PathDiscoverer(platform_type=SupportedPlatform.LINUX)
        with patch.dict(os.environ, {"ED_JOURNAL_DIR": str(env_dir)}):
            result = discoverer.discover_journal_directory(override_path=param_dir)

        assert result.resolved_path == param_dir.resolve()
        assert result.discovery_source == "parameter_override"


class TestPlatformGatingAndUnsupportedPlatform:
    """Tests for platform dispatch and unsupported OS rejection."""

    def test_unsupported_platform_raises_error(self) -> None:
        discoverer = PathDiscoverer(platform_type=SupportedPlatform.UNSUPPORTED)
        with patch("sys.platform", "darwin"):
            with pytest.raises(UnsupportedPlatformError) as exc_info:
                discoverer.discover_journal_directory()

        assert exc_info.value.platform_name == "darwin"


class TestWindowsPathStrategy:
    """Tests for WindowsPathStrategy with Known Folders, Registry, and Environment mocks."""

    def test_windows_strategy_known_folder_success(self, tmp_path: Path) -> None:
        strategy = WindowsPathStrategy()
        saved_games_dir = tmp_path / "Saved Games"
        expected_dir = saved_games_dir / SUBDIR_REL_PATH

        with patch.object(strategy, "_query_known_folder_saved_games", return_value=saved_games_dir):
            with patch.object(strategy, "_query_registry_saved_games", return_value=None):
                candidates = strategy.find_candidates()

        assert expected_dir in candidates
        assert strategy.platform_name == "Microsoft Windows"

    def test_windows_strategy_registry_fallback(self, tmp_path: Path) -> None:
        strategy = WindowsPathStrategy()
        reg_dir = tmp_path / "RegistrySavedGames"
        expected_dir = reg_dir / SUBDIR_REL_PATH

        with patch.object(strategy, "_query_known_folder_saved_games", return_value=None):
            with patch.object(strategy, "_query_registry_saved_games", return_value=reg_dir):
                with patch.dict(os.environ, {}, clear=True):
                    candidates = strategy.find_candidates()

        assert expected_dir in candidates

    def test_windows_strategy_env_fallback(self, tmp_path: Path) -> None:
        strategy = WindowsPathStrategy()
        profile_dir = tmp_path / "UserProfile"
        expected_dir = profile_dir / "Saved Games" / SUBDIR_REL_PATH

        with patch.object(strategy, "_query_known_folder_saved_games", return_value=None):
            with patch.object(strategy, "_query_registry_saved_games", return_value=None):
                with patch.dict(os.environ, {"USERPROFILE": str(profile_dir)}):
                    candidates = strategy.find_candidates()

        assert expected_dir in candidates

    def test_windows_strategy_query_known_folder_exception_safe(self) -> None:
        strategy = WindowsPathStrategy()
        # When ctypes/windll does not exist (e.g. running on Linux CI), returns None
        assert strategy._query_known_folder_saved_games() is None
        assert strategy._query_registry_saved_games() is None

    def test_path_discoverer_windows_end_to_end(self, tmp_path: Path) -> None:
        saved_games_dir = tmp_path / "Saved Games"
        target_dir = saved_games_dir / SUBDIR_REL_PATH
        target_dir.mkdir(parents=True)

        strategy = WindowsPathStrategy()
        with patch.object(strategy, "_query_known_folder_saved_games", return_value=saved_games_dir):
            discoverer = PathDiscoverer(
                strategy=strategy,
                platform_type=SupportedPlatform.WINDOWS,
            )
            result = discoverer.discover_journal_directory()

        assert result.resolved_path == target_dir.resolve()
        assert result.discovery_source == "platform_win32"


class TestLinuxProtonPathStrategy:
    """Tests for Linux Proton/Steam discovery, VDF parsing, and Flatpak prefixes."""

    def test_vdf_parsing_extracts_library_paths(self, tmp_path: Path) -> None:
        strategy = LinuxProtonPathStrategy()
        vdf_content = """
        "libraryfolders"
        {
            "0"
            {
                "path"		"/home/user/.local/share/Steam"
            }
            "1"
            {
                "path"		"/media/fast_ssd/SteamLibrary"
            }
        }
        """
        vdf_file = tmp_path / "libraryfolders.vdf"
        vdf_file.write_text(vdf_content, encoding="utf-8")

        extracted = strategy._parse_library_folders(vdf_file)
        assert Path("/home/user/.local/share/Steam") in extracted
        assert Path("/media/fast_ssd/SteamLibrary") in extracted

    def test_vdf_parsing_invalid_file_graceful(self, tmp_path: Path) -> None:
        strategy = LinuxProtonPathStrategy()
        missing = tmp_path / "missing.vdf"
        assert strategy._parse_library_folders(missing) == ()

    def test_linux_strategy_finds_proton_in_steam_root(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "fake_home"
        steam_dir = fake_home / ".steam" / "steam"
        target_journal = steam_dir / PROTON_REL_PFX
        target_journal.mkdir(parents=True)

        strategy = LinuxProtonPathStrategy()
        with patch("pathlib.Path.home", return_value=fake_home):
            candidates = strategy.find_candidates()

        assert target_journal in candidates
        assert strategy.platform_name == "Linux (Proton / Steam)"

    def test_linux_strategy_custom_wineprefix(self, tmp_path: Path) -> None:
        fake_wine = tmp_path / "custom_wine"
        strategy = LinuxProtonPathStrategy()

        with patch.dict(os.environ, {"WINEPREFIX": str(fake_wine), "USER": "testpilot"}):
            with patch("pathlib.Path.home", return_value=tmp_path / "empty_home"):
                candidates = strategy.find_candidates()

        expected = (
            fake_wine / "drive_c" / "users" / "testpilot" / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
        )
        assert expected in candidates

    def test_path_discoverer_linux_end_to_end(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home_user"
        steam_dir = fake_home / ".steam" / "steam"
        target_journal = steam_dir / PROTON_REL_PFX
        target_journal.mkdir(parents=True)

        strategy = LinuxProtonPathStrategy()
        with patch("pathlib.Path.home", return_value=fake_home):
            discoverer = PathDiscoverer(
                strategy=strategy,
                platform_type=SupportedPlatform.LINUX,
            )
            result = discoverer.discover_journal_directory()

        assert result.resolved_path == target_journal.resolve()
        assert result.discovery_source == "platform_linux"


class TestCandidateExhaustion:
    """Tests for when automated strategies exhaust all candidates without encountering a directory."""

    def test_candidates_exhausted_raises_journal_path_not_found(self, tmp_path: Path) -> None:
        mock_strategy = MagicMock(spec=PathDiscoveryStrategy)
        mock_strategy.platform_name = "Mock Platform"
        mock_strategy.find_candidates.return_value = (
            tmp_path / "missing_one",
            tmp_path / "missing_two",
        )

        discoverer = PathDiscoverer(
            strategy=mock_strategy,
            platform_type=SupportedPlatform.LINUX,
        )

        with pytest.raises(JournalPathNotFoundError) as exc_info:
            discoverer.discover_journal_directory()

        assert len(exc_info.value.inspected_paths) == 2
        assert exc_info.value.platform_name == "Mock Platform"
        assert "missing_one" in str(exc_info.value)
