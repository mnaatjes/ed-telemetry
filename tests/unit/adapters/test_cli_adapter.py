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
