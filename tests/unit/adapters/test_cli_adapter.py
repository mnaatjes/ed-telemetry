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
