"""SQLite persistence driven adapters implementing EgressPort and TelemetryRepositoryPort."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from ed_telemetry.core.ports.driven.telemetry_driven_port import EgressPort, TelemetryRepositoryPort
from ed_telemetry.core.ports.dto.telemetry_dto import (
    TelemetryPayloadDTO,
    TelemetryQueryDTO,
    TelemetryRecordDTO,
)


class SqlitePersistenceManager:
    """Manages SQLite schema initialization and connection pooling in WAL mode."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
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

        with self._manager._lock, self._manager._connect() as conn:
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

        with self._manager._lock, self._manager._connect() as conn:
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

        with self._manager._lock, self._manager._connect() as conn:
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
        with self._manager._lock, self._manager._connect() as conn:
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
