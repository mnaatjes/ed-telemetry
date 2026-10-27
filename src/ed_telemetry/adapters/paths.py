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


def resolve_default_credentials_path(platform: str | None = None) -> Path:
    """Resolve cross-platform credentials path according to OS standards."""
    current_platform = platform or sys.platform

    if current_platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ed-telemetry" / "credentials.json"
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            return Path(user_profile) / ".config" / "ed-telemetry" / "credentials.json"
        try:
            return Path.home() / ".config" / "ed-telemetry" / "credentials.json"
        except (RuntimeError, KeyError):
            return (
                Path(os.environ.get("HOMEDRIVE", "C:") + os.environ.get("HOMEPATH", "\\"))
                / ".config"
                / "ed-telemetry"
                / "credentials.json"
            )

    # Linux / Unix
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "ed-telemetry" / "credentials.json"

    try:
        return Path.home() / ".config" / "ed-telemetry" / "credentials.json"
    except (RuntimeError, KeyError):
        return Path("/tmp") / ".config" / "ed-telemetry" / "credentials.json"


def sanitize_host_path(path: str | Path | None) -> str | None:
    """Sanitize operating system user home paths to prevent environment leakage."""
    if path is None:
        return None
    p_str = str(path)
    user_home = str(Path.home())
    if p_str.startswith(user_home):
        return p_str.replace(user_home, "~", 1)
    return p_str
