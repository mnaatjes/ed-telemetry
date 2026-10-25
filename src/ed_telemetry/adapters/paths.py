"""Cross-platform path resolution for application logs and persistent databases."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_default_log_path(platform: str | None = None) -> Path:
    """Resolve cross-platform rotating log path according to OS standards."""
    current_platform = platform or sys.platform

    if current_platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ed-telemetry" / "logs" / "ed-telemetry.log"
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            return Path(user_profile) / ".cache" / "ed-telemetry" / "logs" / "ed-telemetry.log"
        return Path.home() / ".cache" / "ed-telemetry" / "logs" / "ed-telemetry.log"

    # Linux / SteamDeck / Unix
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "ed-telemetry" / "ed-telemetry.log"

    state_home = Path.home() / ".local" / "state" / "ed-telemetry" / "ed-telemetry.log"
    return state_home


def resolve_default_db_path(platform: str | None = None) -> Path:
    """Resolve cross-platform SQLite database path according to OS standards."""
    current_platform = platform or sys.platform

    if current_platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ed-telemetry" / "telemetry.db"
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            return Path(user_profile) / ".cache" / "ed-telemetry" / "telemetry.db"
        return Path.home() / ".cache" / "ed-telemetry" / "telemetry.db"

    # Linux / SteamDeck / Unix
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "ed-telemetry" / "telemetry.db"

    return Path.home() / ".local" / "share" / "ed-telemetry" / "telemetry.db"
