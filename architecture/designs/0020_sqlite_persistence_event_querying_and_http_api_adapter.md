---
title: "SDD-020: SQLite Persistence, Event Querying, and HTTP/Stream API Driving Adapter"
tags: ["sdd", "persistence", "sqlite", "api", "streaming", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-020: SQLite Persistence, Event Querying, and HTTP/Stream API Driving Adapter

## 1. Executive Summary
This design document defines the structural interfaces, database schema, use cases, and HTTP driving adapter implementing ADR 0022.

## 2. Structural Architecture & Data Flow

```
                      ┌──────────────────────┐
                      │    FileSystemWatcher │
                      └──────────┬───────────┘
                                 │ FileIngestionEventDTO
                                 ▼
                   ┌──────────────────────────────┐
                   │ ProcessTelemetryStreamUseCase│
                   └─────────────┬────────────────┘
                                 │ TelemetryPayloadDTO
                                 ▼
                     ┌──────────────────────────┐
                     │  CompositeEgressAdapter  │
                     └──────┬────────────┬──────┘
                            │            │
            ┌───────────────┘            └───────────────┐
            ▼                                            ▼
┌────────────────────────┐                   ┌────────────────────────┐
│  BufferedQueueAdapter  │                   │  SqliteEgressAdapter   │
│  (In-Memory Buffer)    │                   │  (WAL SQLite DB)       │
└───────────┬────────────┘                   └───────────┬────────────┘
            │                                            │
            │ EventQueuePort                             │ TelemetryRepositoryPort
            ▼                                            ▼
┌──────────────────────────────┐             ┌──────────────────────────────┐
│ StreamTelemetryEventsUseCase │             │  FindTelemetryEventsUseCase  │
└───────────┬──────────────────┘             └───────────┬──────────────────┘
            │                                            │
            └─────────────────┬──────────────────────────┘
                              │ Driving Ports
                              ▼
                   ┌──────────────────────────────┐
                   │        HttpApiAdapter        │
                   │   (REST + SSE Server)        │
                   └──────────────┬───────────────┘
                                  │ HTTP / SSE
                                  ▼
                        [ Downstream Clients ]
```

## 3. SQLite Schema & Persistence Contracts

### 3.1 SQLite Schema (`telemetry.db`)
```sql
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
```

### 3.2 DTOs (`core/ports/dto/telemetry_dto.py`)
- `TelemetryRecordDTO(id: int, event_id: str, topic: str, timestamp: datetime, raw_hash: str | None, payload_json: str, created_at: datetime)`
- `TelemetryQueryDTO(since_id: int | None, topic: str | None, limit: int = 100)`

### 3.3 Ports
- **Driven:** `TelemetryRepositoryPort`:
  - `insert_event(payload: TelemetryPayloadDTO) -> int`
  - `find_events(query: TelemetryQueryDTO) -> tuple[TelemetryRecordDTO, ...]`
  - `get_latest_event(topic: str) -> TelemetryRecordDTO | None`
- **Driving:** `FindTelemetryEventsPort`:
  - `find_events(query: TelemetryQueryDTO) -> tuple[TelemetryRecordDTO, ...]`
- **Driving:** `StreamTelemetryEventsPort`:
  - `stream_events(timeout: float | None = 1.0) -> Iterator[TelemetryPayloadDTO]`

## 4. HTTP API Specifications (`HttpApiAdapter`)
Built on Python `http.server.ThreadingHTTPServer`:
- `GET /api/v1/health` -> `{"status": "ok"}`
- `GET /api/v1/status` -> `WatcherStatusDTO` as JSON
- `GET /api/v1/events?since_id=100&topic=telemetry.journal&limit=50` -> list of records
- `GET /api/v1/stream` -> `text/event-stream` SSE feed
- `POST /api/v1/control/watch` -> body `{"action": "start"|"stop"}`

## 5. Verification Plan
- Unit tests for `SqliteEgressAdapter` and `SqliteRepositoryAdapter`.
- Unit tests for `FindTelemetryEventsUseCase` and `StreamTelemetryEventsUseCase`.
- Driving tests for `HttpApiAdapter` making live HTTP requests against local ephemeral port.
- Verification script `scripts/verify.py` and `scripts/run_wine_tests.sh`.
