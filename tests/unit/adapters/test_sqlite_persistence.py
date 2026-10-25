"""Unit tests for SqlitePersistenceManager, SqliteEgressAdapter, and SqliteRepositoryAdapter."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ed_telemetry.adapters.driven.persistence.sqlite_adapter import (
    SqliteEgressAdapter,
    SqlitePersistenceManager,
    SqliteRepositoryAdapter,
)
from ed_telemetry.core.ports.dto import TelemetryPayloadDTO, TelemetryQueryDTO


class TestSqlitePersistence:
    """Verifies SQLite WAL persistence and indexed queries."""

    def test_insert_and_query_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_telemetry.db"
            manager = SqlitePersistenceManager(db_path=db_file)
            egress = SqliteEgressAdapter(manager=manager)
            repo = SqliteRepositoryAdapter(manager=manager)

            p1 = TelemetryPayloadDTO(
                topic="telemetry.journal",
                timestamp=datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC),
                payload_bytes=b'{"event":"FSDJump","StarSystem":"Sol"}',
                metadata=(("hash", "hash1"),),
            )
            p2 = TelemetryPayloadDTO(
                topic="telemetry.status",
                timestamp=datetime(2026, 10, 25, 12, 0, 1, tzinfo=UTC),
                payload_bytes=b'{"event":"Status","Flags":16}',
                metadata=(("hash", "hash2"),),
            )

            egress.send(p1)
            egress.send(p2)

            # Query all
            all_records = repo.find_events(TelemetryQueryDTO())
            assert len(all_records) == 2
            assert all_records[0].id == 1
            assert all_records[0].topic == "telemetry.journal"
            assert "Sol" in all_records[0].payload_json
            assert all_records[1].id == 2
            assert all_records[1].topic == "telemetry.status"

            # Query with topic filter
            journal_records = repo.find_events(TelemetryQueryDTO(topic="telemetry.journal"))
            assert len(journal_records) == 1
            assert journal_records[0].topic == "telemetry.journal"

            # Query with since_id
            since_records = repo.find_events(TelemetryQueryDTO(since_id=1))
            assert len(since_records) == 1
            assert since_records[0].id == 2

            # Query latest event
            latest = repo.get_latest_event("telemetry.status")
            assert latest is not None
            assert latest.id == 2
            assert latest.topic == "telemetry.status"
