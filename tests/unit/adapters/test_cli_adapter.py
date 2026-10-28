"""Unit tests for CliTelemetryAdapter driving adapter."""

from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from ed_telemetry.bootstrap.container import build_container


class TestCliTelemetryAdapter:
    """Verifies CliTelemetryAdapter commands, arguments, and exit codes."""

    def test_cli_status_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            db_file = Path(tmp_dir) / "test.db"

            container = build_container(journal_dir=win_dir, db_path=db_file)
            adapter = container.cli_adapter

            # 1. Human text status
            buf = io.StringIO()
            with redirect_stdout(buf):
                code, payload = adapter.run(["status"])
            assert code == 0
            assert payload["is_active"] is False
            assert "Watcher State: Idle" in buf.getvalue()

            # 2. JSON status
            buf_json = io.StringIO()
            with redirect_stdout(buf_json):
                code, payload = adapter.run(["status", "--json"])
            assert code == 0
            assert '"is_active": false' in buf_json.getvalue()

    def test_cli_status_game_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            (win_dir / "Status.json").write_text('{"event":"Status","Flags":16}')
            db_file = Path(tmp_dir) / "test.db"

            container = build_container(journal_dir=win_dir, db_path=db_file)
            adapter = container.cli_adapter

            buf = io.StringIO()
            with redirect_stdout(buf):
                code, payload = adapter.run(["status", "game"])
            assert code == 0
            assert payload["exists"] is True
            assert "Game Status Snapshot: Found" in buf.getvalue()

    def test_cli_events_command(self) -> None:
        import time

        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            (win_dir / "Journal.2026-10-09T100000.01.log").write_bytes(b'{"event":"FileHeader","part":1}\n')
            db_file = Path(tmp_dir) / "test.db"

            container = build_container(journal_dir=win_dir, poll_interval=0.05, db_path=db_file)
            container.process_telemetry_stream_use_case.start_streaming()

            with (win_dir / "Journal.2026-10-09T100000.01.log").open("a", encoding="utf-8") as fp:
                fp.write('{"event":"FSDJump","StarSystem":"Eravate"}\n')
                fp.flush()

            time.sleep(0.2)
            container.process_telemetry_stream_use_case.stop_streaming()

            adapter = container.cli_adapter

            buf = io.StringIO()
            with redirect_stdout(buf):
                code, payload = adapter.run(["events", "--limit", "5"])
            assert code == 0
            assert payload["count"] >= 1
            assert "Retrieved" in buf.getvalue()

            # JSON events
            buf_json = io.StringIO()
            with redirect_stdout(buf_json):
                code, payload = adapter.run(["events", "--json"])
            assert code == 0
            assert '"records"' in buf_json.getvalue()

    def test_cli_logs_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            buf = io.StringIO()
            with redirect_stdout(buf):
                code, payload = adapter.run(["logs", "--limit", "10"])
            assert code == 0
            assert "total_retained" in payload
            assert "Diagnostic Logs" in buf.getvalue()

            buf_json = io.StringIO()
            with redirect_stdout(buf_json):
                code, payload = adapter.run(["logs", "--json"])
            assert code == 0
            assert '"records"' in buf_json.getvalue()

    def test_cli_logs_fallback_to_disk_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"
            log_file.write_text(
                "2026-10-25T14:26:10 [INFO] ed_telemetry.server: Daemon started\n"
                "2026-10-25T14:26:11 [ERROR] ed_telemetry.core: Test failure\n",
                encoding="utf-8",
            )
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            from unittest.mock import patch

            with patch("ed_telemetry.adapters.paths.resolve_default_log_path", return_value=log_file):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code, payload = adapter.run(["logs", "--limit", "5"])
                assert code == 0
                assert payload["total_retained"] >= 2
                assert "Test failure" in buf.getvalue()

    def test_cli_serve_fast_fail_on_path_discovery_error(self) -> None:
        from unittest.mock import patch

        from ed_telemetry.adapters.driven.watcher.discovery.exceptions import JournalPathNotFoundError

        with tempfile.TemporaryDirectory() as tmp_dir:
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            with patch.object(
                container.find_journal_path_use_case,
                "find_path",
                side_effect=JournalPathNotFoundError(inspected_paths=[], platform_name="linux"),
            ):
                err_buf = io.StringIO()
                with redirect_stdout(io.StringIO()), patch("sys.stderr", err_buf):
                    code, payload = adapter.run(["serve"])
                assert code == 1
                assert "Failed to discover Elite Dangerous journal directory" in err_buf.getvalue()

    def test_cli_tail_standalone_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            (win_dir / "Journal.2026-10-09T100000.01.log").write_bytes(b'{"event":"FileHeader","part":1}\n')
            db_file = Path(tmp_dir) / "test.db"

            container = build_container(journal_dir=win_dir, poll_interval=0.05, db_path=db_file)
            adapter = container.cli_adapter

            from unittest.mock import patch

            with patch.object(adapter._stream_events_port, "stream_events", side_effect=KeyboardInterrupt):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code, payload = adapter.run(["tail"])
                assert code == 0
                assert "Streaming live telemetry" in buf.getvalue()
                assert "Stopped streaming." in buf.getvalue()

    def test_cli_stream_subcommand_and_events_follow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            from unittest.mock import patch

            with patch.object(adapter, "_handle_stream", return_value=(0, {"streamed": 1})) as mock_stream:
                code_stream, _ = adapter.run(["stream", "--json"])
                assert code_stream == 0
                assert mock_stream.call_count == 1

                code_events, _ = adapter.run(["events", "--follow", "--json"])
                assert code_events == 0
                assert mock_stream.call_count == 2

    def test_cli_logs_follow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            from unittest.mock import patch

            with patch.object(adapter, "_tail_disk_logs", return_value=(0, {"followed": 3})) as mock_tail:
                code, _ = adapter.run(["logs", "--follow"])
                assert code == 0
                assert mock_tail.call_count == 1

    def test_cli_version_flags(self) -> None:
        import pytest

        from ed_telemetry import __version__

        with tempfile.TemporaryDirectory() as tmp_dir:
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            # Test --version
            buf = io.StringIO()
            with pytest.raises(SystemExit) as exc_info:
                with redirect_stdout(buf):
                    adapter.run(["--version"])
            assert exc_info.value.code == 0
            assert f"ed-telemetry {__version__}" in buf.getvalue()

            # Test -v
            buf_short = io.StringIO()
            with pytest.raises(SystemExit) as exc_short:
                with redirect_stdout(buf_short):
                    adapter.run(["-v"])
            assert exc_short.value.code == 0
            assert f"ed-telemetry {__version__}" in buf_short.getvalue()

    def test_cli_auth_show_unauthenticated_guidance(self) -> None:
        import os
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            creds_file = Path(tmp_dir) / "fake_creds.json"
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            target_patch = "ed_telemetry.adapters.driving.cli.main.resolve_default_credentials_path"
            with patch.dict(os.environ, {}, clear=True):
                with patch(target_patch, return_value=creds_file):
                    # 1. Text mode
                    buf_text = io.StringIO()
                    with redirect_stdout(buf_text):
                        code, payload = adapter.run(["auth", "show"])
                    assert code == 0
                    assert payload["api_key"] is None
                    assert "remediation" in payload
                    assert "ed-telemetry auth keygen --register-env" in buf_text.getvalue()

                    # 2. JSON mode
                    buf_json = io.StringIO()
                    with redirect_stdout(buf_json):
                        code_json, payload_json = adapter.run(["auth", "show", "--json"])
                    assert code_json == 0
                    assert payload_json["api_key"] is None
                    assert "remediation" in payload_json
                    assert "Run 'ed-telemetry auth keygen --register-env'" in buf_json.getvalue()

    def test_cli_serve_non_loopback_security_gate(self) -> None:
        import os
        from unittest.mock import MagicMock, patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            (win_dir / "Journal.2026-10-09T100000.01.log").write_bytes(b'{"event":"FileHeader","part":1}\n')
            db_file = Path(tmp_dir) / "test.db"

            container = build_container(journal_dir=win_dir, db_path=db_file)
            adapter = container.cli_adapter

            creds_file = Path(tmp_dir) / "empty_creds.json"
            target_patch = "ed_telemetry.adapters.driving.cli.main.resolve_default_credentials_path"

            with patch.dict(os.environ, {}, clear=True):
                with patch(target_patch, return_value=creds_file):
                    # 1. Non-loopback without API key fails fast
                    err_buf = io.StringIO()
                    with redirect_stdout(io.StringIO()), patch("sys.stderr", err_buf):
                        code, payload = adapter.run(["serve", "--host", "0.0.0.0"])
                    assert code == 1
                    assert "Refusing to bind to non-loopback host '0.0.0.0'" in err_buf.getvalue()
                    assert payload["error"] == "Refusing to bind to non-loopback interface without authentication"

                    # 2. Non-loopback with explicit --allow-insecure succeeds
                    with patch.object(adapter._http_api_adapter, "start"):
                        with patch.object(adapter._process_stream_port, "start_streaming"):
                            mock_running = MagicMock()
                            mock_running.__bool__.side_effect = [True, False]
                            with patch.object(
                                type(adapter._http_api_adapter), "is_running", new_callable=lambda: mock_running
                            ):
                                out_buf = io.StringIO()
                                with redirect_stdout(out_buf):
                                    code, _ = adapter.run(
                                        [
                                            "serve",
                                            "--host",
                                            "0.0.0.0",
                                            "--journal-dir",
                                            str(win_dir),
                                            "--allow-insecure",
                                        ]
                                    )
                                assert code == 0
                                assert (
                                    "SECURITY RISK: Running on non-loopback host in unauthenticated mode"
                                    in out_buf.getvalue()
                                )

                    # 3. Non-loopback with ED_API_KEY environment succeeds
                    with patch.dict(os.environ, {"ED_API_KEY": "test_token"}):
                        with patch.object(adapter._http_api_adapter, "start"):
                            with patch.object(adapter._process_stream_port, "start_streaming"):
                                mock_running = MagicMock()
                                mock_running.__bool__.side_effect = [True, False]
                                with patch.object(
                                    type(adapter._http_api_adapter), "is_running", new_callable=lambda: mock_running
                                ):
                                    out_buf = io.StringIO()
                                    with redirect_stdout(out_buf):
                                        code, _ = adapter.run(
                                            [
                                                "serve",
                                                "--host",
                                                "0.0.0.0",
                                                "--journal-dir",
                                                str(win_dir),
                                            ]
                                        )
                                    assert code == 0
                                    assert "Perimeter Authentication: ENABLED" in out_buf.getvalue()

    def test_cli_stream_authenticated_online_daemon(self) -> None:
        import os
        from unittest.mock import MagicMock, patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            container = build_container(db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            # Mock _probe_daemon to return True
            with patch("ed_telemetry.adapters.driving.cli.main._probe_daemon", return_value=True):
                # 1. When API key is provided, verify it is injected into Authorization header
                mock_resp = MagicMock()
                mock_resp.__enter__.return_value = [
                    b'data: {"topic": "telemetry.status", "payload": "{}"}\n',
                ]
                with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                    with patch.dict(os.environ, {"ED_API_KEY": "test_stream_key"}):
                        out_buf = io.StringIO()
                        with redirect_stdout(out_buf):
                            code, payload = adapter.run(["stream"])
                        assert code == 0
                        assert payload["streamed"] == 1
                        # Assert request had authorization header
                        sent_req = mock_urlopen.call_args[0][0]
                        assert sent_req.headers["Authorization"] == "Bearer test_stream_key"

                # 2. Verify explicit --api-key flag takes precedence on stream and tail
                with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                    out_buf = io.StringIO()
                    with redirect_stdout(out_buf):
                        code, payload = adapter.run(["stream", "--api-key", "explicit_stream_key"])
                    assert code == 0
                    sent_req = mock_urlopen.call_args[0][0]
                    assert sent_req.headers["Authorization"] == "Bearer explicit_stream_key"

                with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                    out_buf = io.StringIO()
                    with redirect_stdout(out_buf):
                        code, payload = adapter.run(["tail", "--api-key", "explicit_tail_key"])
                    assert code == 0
                    sent_req = mock_urlopen.call_args[0][0]
                    assert sent_req.headers["Authorization"] == "Bearer explicit_tail_key"

    def test_cli_serve_socket_collision_eaddrinuse(self) -> None:
        import errno
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            (win_dir / "Journal.01.log").write_bytes(b'{"event":"FileHeader"}\n')
            container = build_container(journal_dir=win_dir, db_path=Path(tmp_dir) / "test.db")
            adapter = container.cli_adapter

            # 1. EADDRINUSE raises clean error and returns code 1
            with patch.object(
                adapter._http_api_adapter, "start", side_effect=OSError(errno.EADDRINUSE, "Address in use")
            ):
                err_buf = io.StringIO()
                with redirect_stdout(io.StringIO()), patch("sys.stderr", err_buf):
                    code, payload = adapter.run(["serve", "--journal-dir", str(win_dir), "--port", "8080"])
                assert code == 1
                assert "Port 8080 is already in use by another process." in err_buf.getvalue()
                assert 'pkill -f "ed-telemetry serve"' in err_buf.getvalue()
                assert payload["error"] == "Address already in use"
                assert payload["port"] == 8080

            # 2. Other OSError (e.g. EACCES) is re-raised
            with patch.object(
                adapter._http_api_adapter, "start", side_effect=OSError(errno.EACCES, "Permission denied")
            ):
                err_buf = io.StringIO()
                import pytest

                with pytest.raises(OSError) as exc_info:
                    with redirect_stdout(io.StringIO()), patch("sys.stderr", err_buf):
                        adapter.run(["serve", "--journal-dir", str(win_dir), "--port", "80"])
                assert exc_info.value.errno == errno.EACCES

    def test_cli_db_status_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_cli_db.db"
            container = build_container(db_path=db_file)
            adapter = container.cli_adapter

            buf = io.StringIO()
            with redirect_stdout(buf):
                code, payload = adapter.run(["db", "status"])
            assert code == 0
            assert payload["total_events"] == 0
            assert "Database Storage Status:" in buf.getvalue()

            buf_json = io.StringIO()
            with redirect_stdout(buf_json):
                code, payload = adapter.run(["db", "status", "--json"])
            assert code == 0
            assert '"total_events": 0' in buf_json.getvalue()

    def test_cli_db_prune_and_vacuum(self) -> None:
        from datetime import UTC, datetime
        from unittest.mock import patch

        from ed_telemetry.core.ports.dto import TelemetryPayloadDTO

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_cli_prune.db"
            container = build_container(db_path=db_file)
            adapter = container.cli_adapter

            # Insert some records via repository/egress
            for i in range(5):
                t = datetime(2026, 10, i + 1, 12, 0, 0, tzinfo=UTC)
                container.process_telemetry_stream_use_case._egress.send(
                    TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t, payload_bytes=b"{}")
                )

            # Test prune with no flags fails
            err_buf = io.StringIO()
            with redirect_stdout(io.StringIO()), patch("sys.stderr", err_buf):
                code, _ = adapter.run(["db", "prune"])
            assert code == 1
            assert "Must specify at least one pruning criteria" in err_buf.getvalue()

            # Test prune --max-records 2 with --force
            buf = io.StringIO()
            with redirect_stdout(buf):
                code, payload = adapter.run(["db", "prune", "--max-records", "2", "--force"])
            assert code == 0
            assert payload["pruned_count"] == 3
            assert "Prune completed: Removed 3 events." in buf.getvalue()

            # Test vacuum
            buf_vac = io.StringIO()
            with redirect_stdout(buf_vac):
                code, payload = adapter.run(["db", "vacuum"])
            assert code == 0
            assert payload["vacuumed"] is True
            assert "Vacuum completed: Reclaimed" in buf_vac.getvalue()

    def test_cli_serve_with_retention_flags(self) -> None:
        from datetime import UTC, datetime
        from unittest.mock import patch

        from ed_telemetry.core.ports.dto import TelemetryPayloadDTO

        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            (win_dir / "Journal.01.log").write_bytes(b'{"event":"FileHeader"}\n')
            db_file = Path(tmp_dir) / "test_retention.db"

            container = build_container(journal_dir=win_dir, db_path=db_file)
            adapter = container.cli_adapter

            # Populate database with historical events to verify startup pruning output
            for i in range(10):
                t = datetime(2026, 9, i + 1, 12, 0, 0, tzinfo=UTC)
                container.process_telemetry_stream_use_case._egress.send(
                    TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t, payload_bytes=b"{}")
                )

            with patch.object(adapter._http_api_adapter, "start"), patch.object(adapter._http_api_adapter, "stop"):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code, _ = adapter.run(
                        [
                            "serve",
                            "--journal-dir",
                            str(win_dir),
                            "--retention-days",
                            "30",
                            "--retention-max-records",
                            "5",
                        ]
                    )
                assert code == 0
                out = buf.getvalue()
                assert "Database Retention: Pruned" in out
