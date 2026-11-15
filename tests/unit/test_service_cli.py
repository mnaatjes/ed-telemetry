"""Unit tests for OS service CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ed_telemetry.adapters.driving.cli.service import control_service, install_service


def test_install_service_linux(tmp_path: Path, monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("sys.platform", "linux")

    with patch("subprocess.run") as mock_run:
        cmd = install_service("ed-telemetry")

    assert cmd == ["systemctl", "--user", "enable", "--now", "ed-telemetry.service"]
    assert (tmp_path / ".config" / "systemd" / "user" / "ed-telemetry.service").exists()
    assert mock_run.call_count == 2


def test_control_service_status(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    with patch("subprocess.run") as mock_run:
        cmd = control_service("status")

    assert cmd == ["systemctl", "--user", "status", "ed-telemetry.service"]
    mock_run.assert_called_once()
