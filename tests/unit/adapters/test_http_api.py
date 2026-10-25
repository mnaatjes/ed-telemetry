"""Unit tests for HttpApiAdapter driving adapter."""

from __future__ import annotations

import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from ed_telemetry.bootstrap.container import build_container


class TestHttpApiAdapter:
    """Verifies HttpApiAdapter endpoints on ephemeral port."""

    def test_http_api_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            win_dir = Path(tmp_dir) / "journals"
            win_dir.mkdir()
            (win_dir / "Journal.2026-10-09T100000.01.log").write_bytes(b'{"event":"FileHeader","part":1}\n')
            (win_dir / "Status.json").write_text('{"event":"Status","Flags":16}')

            db_file = Path(tmp_dir) / "test.db"

            # Ephemeral port 0 and fast poll interval 0.05
            container = build_container(journal_dir=win_dir, poll_interval=0.05, db_path=db_file, http_port=0)
            server = container.http_api_adapter
            server.start()

            try:
                base_url = f"http://127.0.0.1:{server.port}"

                # 1. /api/v1/health
                with urllib.request.urlopen(f"{base_url}/api/v1/health") as resp:
                    assert resp.status == 200
                    data = json.loads(resp.read().decode("utf-8"))
                    assert data["status"] == "ok"

                # 2. /api/v1/status
                with urllib.request.urlopen(f"{base_url}/api/v1/status") as resp:
                    assert resp.status == 200
                    status_data = json.loads(resp.read().decode("utf-8"))
                    assert status_data["is_active"] is False

                # 3. /api/v1/status/game
                with urllib.request.urlopen(f"{base_url}/api/v1/status/game") as resp:
                    assert resp.status == 200
                    game_data = json.loads(resp.read().decode("utf-8"))
                    assert game_data["exists"] is True

                # 4. /api/v1/control/watch (start)
                req = urllib.request.Request(
                    f"{base_url}/api/v1/control/watch",
                    data=json.dumps({"action": "start"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as resp:
                    assert resp.status == 200
                    ctrl_data = json.loads(resp.read().decode("utf-8"))
                    assert ctrl_data["action"] == "start"

                # Append line to journal
                with (win_dir / "Journal.2026-10-09T100000.01.log").open("a", encoding="utf-8") as fp:
                    fp.write('{"event":"FSDJump","StarSystem":"Eravate"}\n')
                    fp.flush()

                import time

                # Wait for poll tick
                time.sleep(0.25)

                # 5. /api/v1/control/watch (stop)
                req_stop = urllib.request.Request(
                    f"{base_url}/api/v1/control/watch",
                    data=json.dumps({"action": "stop"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_stop) as resp:
                    assert resp.status == 200

                # 6. /api/v1/events (Query historical events from SQLite)
                with urllib.request.urlopen(f"{base_url}/api/v1/events") as resp:
                    assert resp.status == 200
                    events = json.loads(resp.read().decode("utf-8"))
                    assert len(events) > 0
                    assert any("Eravate" in e["payload_json"] or "FileHeader" in e["payload_json"] for e in events)

                # 7. /api/v1/events/buffer (Read and drain in-memory buffer)
                with urllib.request.urlopen(f"{base_url}/api/v1/events/buffer") as resp:
                    assert resp.status == 200
                    batch = json.loads(resp.read().decode("utf-8"))
                    assert "events" in batch
                    assert "remaining_count" in batch
                    assert "dropped_count" in batch
                    assert len(batch["events"]) >= 1

                # 8. /api/v1/snapshots/{name} (Valid snapshot)
                (win_dir / "Market.json").write_text('{"event":"Market","StationName":"Sol"}')
                with urllib.request.urlopen(f"{base_url}/api/v1/snapshots/market") as resp:
                    assert resp.status == 200
                    snap_data = json.loads(resp.read().decode("utf-8"))
                    assert snap_data["exists"] is True
                    assert "Market" in snap_data["raw_payload"]

                # 9. /api/v1/snapshots/{name} (Missing snapshot -> RFC 7807 Problem Details 404)
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(f"{base_url}/api/v1/snapshots/nonexistent")
                assert exc_info.value.code == 404
                assert exc_info.value.headers.get("Content-Type") == "application/problem+json"
                problem = json.loads(exc_info.value.read().decode("utf-8"))
                assert problem["title"] == "Snapshot Not Found"
                assert problem["status"] == 404

                # 10. POST /api/v1/control/watch (Invalid action -> RFC 7807 Problem Details 400)
                bad_req = urllib.request.Request(
                    f"{base_url}/api/v1/control/watch",
                    data=b'{"action":"invalid"}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with pytest.raises(urllib.error.HTTPError) as exc_info_bad:
                    urllib.request.urlopen(bad_req)
                assert exc_info_bad.value.code == 400
                assert exc_info_bad.value.headers.get("Content-Type") == "application/problem+json"
                problem = json.loads(exc_info_bad.value.read().decode("utf-8"))
                assert problem["title"] == "Bad Request"
                # 11. /api/v1/diagnostics/logs (Diagnostics log buffer)
                with urllib.request.urlopen(f"{base_url}/api/v1/diagnostics/logs?limit=10") as resp:
                    assert resp.status == 200
                    diag_data = json.loads(resp.read().decode("utf-8"))
                    assert "records" in diag_data
                    assert "total_retained" in diag_data

            finally:
                server.stop()
