"""Linux Steam Play / Proton and Wine path discovery strategy."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path

STEAM_APP_ID = "359320"
PROTON_REL_PFX = (
    Path("steamapps")
    / "compatdata"
    / STEAM_APP_ID
    / "pfx"
    / "drive_c"
    / "users"
    / "steamuser"
    / "Saved Games"
    / "Frontier Developments"
    / "Elite Dangerous"
)


class LinuxProtonPathStrategy:
    """Strategy for discovering Elite Dangerous journal directories under Linux Proton / Steam."""

    @property
    def platform_name(self) -> str:
        """The platform identifier associated with this strategy."""
        return "Linux (Proton / Steam)"

    def find_candidates(self) -> Sequence[Path]:
        """
        Enumerate candidate directory paths on Linux in prioritized order:
        1. Enumerate all Steam libraries via libraryfolders.vdf.
        2. Standard Steam installation roots (~/.steam/steam, ~/.local/share/Steam).
        3. Flatpak Steam installation root (~/.var/app/com.valvesoftware.Steam).
        4. Custom WINEPREFIX environment if set.
        """
        candidates: list[Path] = []
        home = Path.home()

        # Potential Steam installation roots
        steam_roots = (
            home / ".steam" / "steam",
            home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        )

        # 1. Enumerate library folders across detected Steam roots
        for steam_root in steam_roots:
            vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
            if vdf_path.is_file():
                for library_root in self._parse_library_folders(vdf_path):
                    candidate = library_root / PROTON_REL_PFX
                    if candidate not in candidates:
                        candidates.append(candidate)

        # 2. Check direct default roots
        for steam_root in steam_roots:
            candidate = steam_root / PROTON_REL_PFX
            if candidate not in candidates:
                candidates.append(candidate)

        # 3. Check active $WINEPREFIX
        wine_prefix = os.environ.get("WINEPREFIX")
        if wine_prefix:
            wine_root = Path(wine_prefix)
            # Standalone Wine or Proton might use active user or steamuser
            for user in ("steamuser", os.environ.get("USER", "user")):
                wine_candidate = (
                    wine_root / "drive_c" / "users" / user / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
                )
                if wine_candidate not in candidates:
                    candidates.append(wine_candidate)

        return tuple(candidates)

    def _parse_library_folders(self, vdf_path: Path) -> Sequence[Path]:
        """
        Parse Steam's libraryfolders.vdf to extract external library root paths.
        Supports standard Valve KeyValues format using lightweight regex extraction.
        """
        libraries: list[Path] = []
        try:
            content = vdf_path.read_text(encoding="utf-8", errors="replace")
            # Matches: "path"		"/media/games/SteamLibrary"
            matches = re.findall(r'"path"\s+"([^"]+)"', content)
            for raw_path in matches:
                lib_path = Path(raw_path)
                if lib_path not in libraries:
                    libraries.append(lib_path)
        except Exception:
            return ()

        return tuple(libraries)
