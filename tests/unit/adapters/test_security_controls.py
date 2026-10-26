"""Unit tests for perimeter network guarding, storage hardening, and sensitive telemetry controls."""

from __future__ import annotations

import json
import os
import stat
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ed_telemetry.adapters.driven.persistence.sqlite_adapter import SqlitePersistenceManager
from ed_telemetry.adapters.driving.api.server import HttpApiAdapter
from ed_telemetry.adapters.driving.cli.main import CliTelemetryAdapter
from ed_telemetry.adapters.paths import sanitize_host_path
from ed_telemetry.core.ports.dto.telemetry_dto import WatcherStatusDTO


def test_posix_permissions_enforced_on_sqlite_db(tmp_path: Path) -> None:
    """Verify that SqlitePersistenceManager enforces 0700 on dir and 0600 on db files."""
    db_dir = tmp_path / "secured_storage"
    db_file = db_dir / "telemetry.db"

    manager = SqlitePersistenceManager(db_path=db_file)

    if os.name == "posix":
        dir_mode = stat.S_IMODE(os.stat(db_dir).st_mode)
        file_mode = stat.S_IMODE(os.stat(db_file).st_mode)
        assert dir_mode == 0o700, f"Expected 0700 dir mode, got {oct(dir_mode)}"
        assert file_mode == 0o600, f"Expected 0600 file mode, got {oct(file_mode)}"

    # Check WAL file if generated
    with manager.connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INT);")
    manager._secure_db_files()


def test_sanitize_host_path() -> None:
    """Verify that sanitize_host_path replaces home directory prefix with ~."""
    home = Path.home()
    full_path = home / ".local" / "share" / "ed-telemetry" / "telemetry.db"
    assert sanitize_host_path(full_path) == "~/.local/share/ed-telemetry/telemetry.db"
    assert sanitize_host_path(str(full_path)) == "~/.local/share/ed-telemetry/telemetry.db"
    assert sanitize_host_path(None) is None

    foreign_path = "/var/log/ed-telemetry.log"
    assert sanitize_host_path(foreign_path) == foreign_path


def test_http_api_unauthenticated_mode() -> None:
    """Verify unauthenticated requests succeed when api_key is None (local mode)."""
    watcher_mock = MagicMock()
    watcher_mock.get_status.return_value = WatcherStatusDTO(
        is_active=True,
        monitored_directory="/path/to/journal",
        active_journal="Journal.01.log",
    )

    server = HttpApiAdapter(
        host="127.0.0.1",
        port=0,
        api_key=None,
        watcher_status_port=watcher_mock,
    )
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}/api/v1/status"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["is_active"] is True
    finally:
        server.stop()


def test_http_api_authenticated_bearer_and_x_api_key_and_query() -> None:
    """Verify API key authentication via Bearer, X-API-Key, and query param."""
    watcher_mock = MagicMock()
    watcher_mock.get_status.return_value = WatcherStatusDTO(
        is_active=True,
        monitored_directory="/path/to/journal",
        active_journal=None,
    )

    api_key = "ed_sec_0123456789abcdef0123456789abcdef0123456789abcdef"
    server = HttpApiAdapter(
        host="127.0.0.1",
        port=0,
        api_key=api_key,
        watcher_status_port=watcher_mock,
    )
    server.start()
    try:
        base_url = f"http://127.0.0.1:{server.port}/api/v1/status"

        # 1. Unauthenticated request should fail with 401
        req_unauth = urllib.request.Request(base_url, method="GET")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_unauth)
        assert exc_info.value.code == 401
        err_body = json.loads(exc_info.value.read().decode("utf-8"))
        assert err_body["status"] == 401
        assert err_body["title"] == "Unauthorized"

        # 2. Authenticated via Bearer
        req_bearer = urllib.request.Request(base_url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req_bearer) as resp:
            assert resp.status == 200

        # 3. Authenticated via X-API-Key
        req_x_key = urllib.request.Request(base_url, headers={"X-API-Key": api_key})
        with urllib.request.urlopen(req_x_key) as resp:
            assert resp.status == 200

        # 4. Authenticated via query parameter
        req_query = urllib.request.Request(f"{base_url}?api_key={api_key}")
        with urllib.request.urlopen(req_query) as resp:
            assert resp.status == 200

        # 5. Invalid token should fail with 401
        req_invalid = urllib.request.Request(base_url, headers={"Authorization": "Bearer wrong_key"})
        with pytest.raises(urllib.error.HTTPError) as exc_invalid:
            urllib.request.urlopen(req_invalid)
        assert exc_invalid.value.code == 401
    finally:
        server.stop()


def test_cors_origin_policy_and_preflight() -> None:
    """Verify CORS origin evaluation and OPTIONS preflight behavior."""
    server = HttpApiAdapter(
        host="127.0.0.1",
        port=0,
        api_key=None,
        allowed_origins=("http://localhost", "https://dashboard.example.local"),
    )
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}/api/v1/health"

        # 1. Allowed origin (loopback)
        req1 = urllib.request.Request(url, headers={"Origin": "http://127.0.0.1:3000"})
        with urllib.request.urlopen(req1) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:3000"

        # 2. Allowed explicit remote origin
        req2 = urllib.request.Request(url, headers={"Origin": "https://dashboard.example.local"})
        with urllib.request.urlopen(req2) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") == "https://dashboard.example.local"

        # 3. Disallowed origin
        req3 = urllib.request.Request(url, headers={"Origin": "https://malicious-site.com"})
        with urllib.request.urlopen(req3) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") is None

        # 4. OPTIONS preflight
        req_opt = urllib.request.Request(url, headers={"Origin": "http://localhost:8080"}, method="OPTIONS")
        with urllib.request.urlopen(req_opt) as resp:
            assert resp.status == 204
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:8080"
            assert "GET, POST, OPTIONS" in resp.headers.get("Access-Control-Allow-Methods", "")
    finally:
        server.stop()


def test_cli_auth_keygen_show_revoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CLI auth keygen, show, and revoke subcommands with temporary credentials."""
    creds_dir = tmp_path / ".config" / "ed-telemetry"
    creds_file = creds_dir / "credentials.json"
    fake_rc = tmp_path / ".bashrc"
    fake_rc.write_text("# existing bashrc\n")

    monkeypatch.setattr("ed_telemetry.adapters.paths.resolve_default_credentials_path", lambda: creds_file)
    monkeypatch.setattr("ed_telemetry.adapters.driving.cli.main.resolve_default_credentials_path", lambda: creds_file)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.delenv("ED_API_KEY", raising=False)

    cli = CliTelemetryAdapter(
        watcher_status_port=MagicMock(),
        game_status_port=MagicMock(),
        find_events_port=MagicMock(),
        process_stream_port=MagicMock(),
        http_api_adapter=MagicMock(),
    )

    # 1. Keygen without force
    code, payload = cli.run(["auth", "keygen", "--register-env"])
    assert code == 0
    token = payload["api_key"]
    assert token.startswith("ed_sec_")
    assert len(token) == len("ed_sec_") + 48  # 55 chars
    assert creds_file.exists()

    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(creds_file).st_mode)
        assert mode == 0o600

    # Verify bashrc registration
    bashrc_content = fake_rc.read_text()
    assert f'export ED_API_KEY="{token}"' in bashrc_content

    # 2. Keygen duplicate without force should error
    code_dup, _ = cli.run(["auth", "keygen"])
    assert code_dup == 1

    # 3. Keygen with --force should succeed and replace
    code_force, payload_force = cli.run(["auth", "keygen", "--force", "--register-env"])
    assert code_force == 0
    new_token = payload_force["api_key"]
    assert new_token != token
    assert f'export ED_API_KEY="{new_token}"' in fake_rc.read_text()

    # 4. Show active key from credentials file
    code_show, payload_show = cli.run(["auth", "show"])
    assert code_show == 0
    assert payload_show["api_key"] == new_token
    assert "file" in payload_show["source"]

    # 5. Revoke removes credentials and cleans bashrc
    code_revoke, payload_revoke = cli.run(["auth", "revoke"])
    assert code_revoke == 0
    assert not creds_file.exists()
    assert "ED_API_KEY" not in fake_rc.read_text()
