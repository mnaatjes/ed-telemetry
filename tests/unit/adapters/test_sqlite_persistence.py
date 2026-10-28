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

    def test_database_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_stats.db"
            manager = SqlitePersistenceManager(db_path=db_file)
            egress = SqliteEgressAdapter(manager=manager)
            repo = SqliteRepositoryAdapter(manager=manager)

            # Initially empty stats
            stats = repo.get_database_stats()
            assert stats.total_events == 0
            assert stats.db_path == str(db_file)
            assert stats.oldest_event_timestamp is None
            assert stats.newest_event_timestamp is None
            assert stats.file_size_bytes > 0

            # Insert payloads
            t1 = datetime(2026, 10, 20, 10, 0, 0, tzinfo=UTC)
            t2 = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
            egress.send(TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t1, payload_bytes=b"{}"))
            egress.send(TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t2, payload_bytes=b"{}"))

            stats_after = repo.get_database_stats()
            assert stats_after.total_events == 2
            assert stats_after.oldest_event_timestamp == t1
            assert stats_after.newest_event_timestamp == t2

    def test_prune_events_older_than(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_prune_age.db"
            manager = SqlitePersistenceManager(db_path=db_file)
            egress = SqliteEgressAdapter(manager=manager)
            repo = SqliteRepositoryAdapter(manager=manager)

            t1 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
            t2 = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
            t3 = datetime(2026, 10, 27, 10, 0, 0, tzinfo=UTC)

            egress.send(TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t1, payload_bytes=b"{}"))
            egress.send(TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t2, payload_bytes=b"{}"))
            egress.send(TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t3, payload_bytes=b"{}"))

            # Prune older than 2026-10-20
            cutoff = datetime(2026, 10, 20, 0, 0, 0, tzinfo=UTC)
            deleted = repo.prune_events(older_than=cutoff)
            assert deleted == 2

            stats = repo.get_database_stats()
            assert stats.total_events == 1
            assert stats.oldest_event_timestamp == t3

    def test_prune_events_max_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_prune_max.db"
            manager = SqlitePersistenceManager(db_path=db_file)
            egress = SqliteEgressAdapter(manager=manager)
            repo = SqliteRepositoryAdapter(manager=manager)

            for i in range(10):
                t = datetime(2026, 10, i + 1, 12, 0, 0, tzinfo=UTC)
                egress.send(TelemetryPayloadDTO(topic="telemetry.journal", timestamp=t, payload_bytes=b"{}"))

            # Retain only newest 3
            deleted = repo.prune_events(max_records=3)
            assert deleted == 7

            stats = repo.get_database_stats()
            assert stats.total_events == 3
            assert stats.newest_event_timestamp == datetime(2026, 10, 10, 12, 0, 0, tzinfo=UTC)

    def test_vacuum_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "test_vacuum.db"
            manager = SqlitePersistenceManager(db_path=db_file)
            egress = SqliteEgressAdapter(manager=manager)
            repo = SqliteRepositoryAdapter(manager=manager)

            for _ in range(20):
                egress.send(
                    TelemetryPayloadDTO(
                        topic="telemetry.journal",
                        timestamp=datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC),
                        payload_bytes=b"x" * 1024,
                    )
                )
            repo.prune_events(max_records=0)
            # Vacuum should succeed without error
            repo.vacuum()
            stats = repo.get_database_stats()
            assert stats.total_events == 0
