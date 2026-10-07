"""Windows native path discovery strategy using Win32 Shell API and Registry."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

# FOLDERID_SavedGames GUID: {4C5C32FF-BB9D-43b0-B5B4-2D780DDF04E3}
FOLDERID_SAVED_GAMES_GUID = "{4C5C32FF-BB9D-43b0-B5B4-2D780DDF04E3}"
SUBDIR_REL_PATH = Path("Frontier Developments") / "Elite Dangerous"


class WindowsPathStrategy:
    """Strategy for discovering Elite Dangerous journal directories on Microsoft Windows."""

    @property
    def platform_name(self) -> str:
        """The platform identifier associated with this strategy."""
        return "Microsoft Windows"

    def find_candidates(self) -> Sequence[Path]:
        """
        Enumerate candidate directory paths on Windows in prioritized order:
        1. Win32 Known Folder Shell API (FOLDERID_SavedGames).
        2. Windows Registry (User Shell Folders).
        3. Standard %USERPROFILE%\\Saved Games fallback.
        """
        candidates: list[Path] = []

        # 1. Shell API FOLDERID_SavedGames
        known_folder = self._query_known_folder_saved_games()
        if known_folder is not None:
            candidates.append(known_folder / SUBDIR_REL_PATH)

        # 2. Windows Registry
        registry_folder = self._query_registry_saved_games()
        if registry_folder is not None:
            candidate = registry_folder / SUBDIR_REL_PATH
            if candidate not in candidates:
                candidates.append(candidate)

        # 3. Environment Fallback
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            fallback = Path(user_profile) / "Saved Games" / SUBDIR_REL_PATH
            if fallback not in candidates:
                candidates.append(fallback)

        return tuple(candidates)

    def _query_known_folder_saved_games(self) -> Path | None:
        """Query SHGetKnownFolderPath via ctypes for FOLDERID_SavedGames."""
        try:
            import ctypes
            from ctypes import wintypes

            # GUID structure for {4C5C32FF-BB9D-43b0-B5B4-2D780DDF04E3}
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_byte * 8),
                ]

            folderid_saved_games = GUID(
                0x4C5C32FF,
                0xBB9D,
                0x43B0,
                (ctypes.c_byte * 8)(0xB5, 0xB4, 0x2D, 0x78, 0x0D, 0xDF, 0x04, 0xE3),
            )

            # On non-Windows platforms ctypes has no windll attribute
            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return None

            shell32 = windll.shell32
            ole32 = windll.ole32

            path_ptr = wintypes.LPWSTR()
            result = shell32.SHGetKnownFolderPath(ctypes.byref(folderid_saved_games), 0, None, ctypes.byref(path_ptr))

            if result == 0 and path_ptr.value:
                resolved_str = str(path_ptr.value)
                ole32.CoTaskMemFree(path_ptr)
                return Path(resolved_str)
        except Exception:
            return None

        return None

    def _query_registry_saved_games(self) -> Path | None:
        """Query Windows Registry User Shell Folders for Saved Games."""
        try:
            import winreg

            open_key = getattr(winreg, "OpenKey", None)
            query_val = getattr(winreg, "QueryValueEx", None)
            hkey_cu = getattr(winreg, "HKEY_CURRENT_USER", None)

            if open_key is None or query_val is None or hkey_cu is None:
                return None

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with open_key(hkey_cu, key_path) as key:
                val, _val_type = query_val(key, FOLDERID_SAVED_GAMES_GUID)
                if val:
                    expanded = os.path.expandvars(str(val))
                    return Path(expanded)
        except Exception:
            return None

        return None
