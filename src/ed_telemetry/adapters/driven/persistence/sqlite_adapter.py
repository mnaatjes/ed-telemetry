"""SQLite persistence driven adapters implementing EgressPort and TelemetryRepositoryPort."""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from ed_telemetry.core.ports.driven.telemetry_driven_port import EgressPort, TelemetryRepositoryPort
from ed_telemetry.core.ports.dto.telemetry_dto import (
    TelemetryPayloadDTO,
    TelemetryQueryDTO,
    TelemetryRecordDTO,
)


def _enforce_posix_permissions(path: Path, is_dir: bool = False) -> None:
    """Enforce POSIX permissions (0700 for directories, 0600 for files) if on POSIX."""
    if os.name == "posix" and path.exists():
        target_mode = 0o700 if is_dir else 0o600
        try:
            os.chmod(path, target_mode)
        except OSError:
            pass


class SqlitePersistenceManager:
    """Manages SQLite schema initialization and connection management in WAL mode."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        _enforce_posix_permissions(self.db_path.parent, is_dir=True)
        self._lock = threading.Lock()
        self._init_schema()
        self._secure_db_files()

    def _secure_db_files(self) -> None:
        """Enforce strict permissions on the SQLite database and auxiliary WAL/SHM files."""
        for suffix in ("", "-wal", "-shm"):
            target = Path(f"{self.db_path}{suffix}")
            _enforce_posix_permissions(target, is_dir=False)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a managed sqlite3 connection that always closes cleanly upon exit."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    raw_hash TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_telemetry_topic ON telemetry_events(topic);
                CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry_events(timestamp);
                """
            )


class SqliteEgressAdapter(EgressPort):
    """Driven adapter persisting outbound telemetry events into SQLite table in WAL mode."""

    def __init__(self, manager: SqlitePersistenceManager) -> None:
        self._manager = manager

    def send(self, payload: TelemetryPayloadDTO) -> None:
        """Insert payload into SQLite events table."""
        # Convert raw payload bytes to UTF-8 text/JSON
        payload_str = payload.payload_bytes.decode("utf-8", errors="replace")
        created_at_str = datetime.now(UTC).isoformat()
        timestamp_str = payload.timestamp.isoformat()
        raw_hash = dict(payload.metadata).get("hash")

        with self._manager._lock, self._manager.connection() as conn:
            conn.execute(
                """
                INSERT INTO telemetry_events (event_id, topic, timestamp, raw_hash, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{payload.topic}_{payload.timestamp.timestamp()}",
                    payload.topic,
                    timestamp_str,
                    raw_hash,
                    payload_str,
                    created_at_str,
                ),
            )
            conn.commit()


class SqliteRepositoryAdapter(TelemetryRepositoryPort):
    """Driven adapter querying historical telemetry events from SQLite."""

    def __init__(self, manager: SqlitePersistenceManager) -> None:
        self._manager = manager

    def insert_event(self, payload: TelemetryPayloadDTO) -> int:
        """Insert single event and return primary key id."""
        payload_str = payload.payload_bytes.decode("utf-8", errors="replace")
        created_at_str = datetime.now(UTC).isoformat()
        timestamp_str = payload.timestamp.isoformat()
        raw_hash = dict(payload.metadata).get("hash")

        with self._manager._lock, self._manager.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO telemetry_events (event_id, topic, timestamp, raw_hash, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{payload.topic}_{payload.timestamp.timestamp()}",
                    payload.topic,
                    timestamp_str,
                    raw_hash,
                    payload_str,
                    created_at_str,
                ),
            )
            conn.commit()
            return int(cur.lastrowid or 0)

    def find_events(self, query: TelemetryQueryDTO) -> tuple[TelemetryRecordDTO, ...]:
        """Query events matching filter criteria."""
        clauses: list[str] = []
        params: list[object] = []

        if query.since_id is not None:
            clauses.append("id > ?")
            params.append(query.since_id)

        if query.topic is not None:
            clauses.append("topic = ?")
            params.append(query.topic)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            "SELECT id, event_id, topic, timestamp, raw_hash, payload_json, created_at "
            f"FROM telemetry_events {where_sql} ORDER BY id ASC LIMIT ?"
        )
        params.append(query.limit if query.limit > 0 else 100)

        with self._manager._lock, self._manager.connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        records: list[TelemetryRecordDTO] = []
        for r in rows:
            ts = datetime.fromisoformat(r["timestamp"])
            cat = datetime.fromisoformat(r["created_at"])
            records.append(
                TelemetryRecordDTO(
                    id=r["id"],
                    event_id=r["event_id"],
                    topic=r["topic"],
                    timestamp=ts,
                    raw_hash=r["raw_hash"],
                    payload_json=r["payload_json"],
                    created_at=cat,
                )
            )
        return tuple(records)

    def get_latest_event(self, topic: str) -> TelemetryRecordDTO | None:
        """Fetch the most recent event for a given topic."""
        sql = (
            "SELECT id, event_id, topic, timestamp, raw_hash, payload_json, created_at "
            "FROM telemetry_events WHERE topic = ? ORDER BY id DESC LIMIT 1"
        )
        with self._manager._lock, self._manager.connection() as conn:
            row = conn.execute(sql, (topic,)).fetchone()

        if row is None:
            return None

        return TelemetryRecordDTO(
            id=row["id"],
            event_id=row["event_id"],
            topic=row["topic"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            raw_hash=row["raw_hash"],
            payload_json=row["payload_json"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
