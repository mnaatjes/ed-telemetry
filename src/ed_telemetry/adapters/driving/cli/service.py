"""OS service lifecycle CLI commands (install, start, stop, status, uninstall)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SYSTEMD_UNIT_TEMPLATE = """[Unit]
Description=Elite Dangerous Telemetry Daemon
After=network.target

[Service]
ExecStart={exec_start}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def systemd_unit_path() -> Path:
    """Return the user systemd unit file path."""
    return Path.home() / ".config" / "systemd" / "user" / "ed-telemetry.service"


def install_service(exec_start: str | None = None) -> list[str]:
    """Install and enable the OS background service."""
    import shutil

    if exec_start is None:
        exe = shutil.which("ed-telemetry") or str(Path.home() / ".local" / "bin" / "ed-telemetry")
        exec_start = f"{exe} serve"

    if sys.platform == "win32":
        cmd = [
            "schtasks",
            "/Create",
            "/TN",
            "ed-telemetry",
            "/TR",
            exec_start,
            "/SC",
            "ONLOGON",
            "/F",
        ]
        subprocess.run(cmd, check=True)
        return cmd

    unit_file = systemd_unit_path()
    unit_file.parent.mkdir(parents=True, exist_ok=True)
    unit_file.write_text(SYSTEMD_UNIT_TEMPLATE.format(exec_start=exec_start), encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    cmd = ["systemctl", "--user", "enable", "--now", "ed-telemetry.service"]
    subprocess.run(cmd, check=True)
    return cmd


def control_service(action: str) -> list[str]:
    """Run start, stop, status, or uninstall on the OS service."""
    if action not in {"start", "stop", "status", "uninstall"}:
        raise ValueError(f"Unsupported service action: {action}")

    if sys.platform == "win32":
        mapping = {
            "start": ["schtasks", "/Run", "/TN", "ed-telemetry"],
            "stop": ["schtasks", "/End", "/TN", "ed-telemetry"],
            "status": ["schtasks", "/Query", "/TN", "ed-telemetry"],
            "uninstall": ["schtasks", "/Delete", "/TN", "ed-telemetry", "/F"],
        }
        cmd = mapping[action]
        subprocess.run(cmd, check=True)
        return cmd

    if action == "uninstall":
        subprocess.run(["systemctl", "--user", "disable", "--now", "ed-telemetry.service"], check=False)
        unit_file = systemd_unit_path()
        if unit_file.exists():
            unit_file.unlink()
        cmd = ["systemctl", "--user", "daemon-reload"]
        subprocess.run(cmd, check=True)
        return cmd

    cmd = ["systemctl", "--user", action, "ed-telemetry.service"]
    subprocess.run(cmd, check=True)
    return cmd
