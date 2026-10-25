---
title: "ADR 0022: SQLite Persistence, Event Querying, and HTTP/Stream API Driving Adapter"
tags: ["adr", "persistence", "sqlite", "api", "streaming", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0022: SQLite Persistence, Event Querying, and HTTP/Stream API Driving Adapter

## Status
Accepted

## Context
In ADR 0020 and ADR 0021, `ed-telemetry` established its strict ingestion scope and in-memory buffered egress architecture. To serve downstream companion applications (web dashboards, Discord bots, trade tools) in a decoupled ecosystem without requiring external database servers or non-standard framework dependencies:
1. Telemetry payloads must be persisted locally in an append-only, crash-resilient store.
2. Downstream applications need the capability to query historical events with indexing and catch-up pagination.
3. Downstream applications require a local HTTP and real-time streaming endpoint (SSE / chunked JSON stream) to consume events live.
4. Driving adapters must strictly interact with Use Cases, never directly with persistence stores or egress buffers.

## Decision

1. **SQLite Driven Adapters (`adapters/driven/persistence/`):**
   - Implement `SqliteEgressAdapter` satisfying `EgressPort` to insert raw telemetry payloads as UTF-8 JSON text in an append-only SQLite database (`telemetry.db`).
   - Enable SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and synchronous normal mode for high-throughput concurrent writes and non-blocking reads.
   - Implement `SqliteRepositoryAdapter` satisfying `TelemetryRepositoryPort` to query historical events (`find_events`, `get_latest_event`).

2. **Historical Querying & Live Stream Use Cases (`core/use_cases/`):**
   - Declare driven port `TelemetryRepositoryPort` in `core/ports/driven/telemetry_driven_port.py`.
   - Declare driving port `FindTelemetryEventsPort` and implement `FindTelemetryEventsUseCase` in `core/use_cases/find_telemetry_events.py`.
   - Declare driving port `StreamTelemetryEventsPort` and implement `StreamTelemetryEventsUseCase` in `core/use_cases/stream_telemetry_events.py` yielding live events from `EventQueuePort`.

3. **Composite Outbound Dispatch:**
   - Implement `CompositeEgressAdapter` allowing simultaneous fan-out of `TelemetryPayloadDTO` to both the in-memory buffer (`BufferedQueueAdapter`) and disk persistence (`SqliteEgressAdapter`).

4. **Zero-Dependency HTTP API Driving Adapter (`adapters/driving/api/`):**
   - Implement `HttpApiAdapter` using Python standard library `http.server` / `threading` to avoid third-party server frameworks.
   - Routes:
     - `GET /api/v1/health` & `GET /api/v1/status`: Operational state from `GetWatcherStatusUseCase`.
     - `GET /api/v1/events`: Historical querying via `FindTelemetryEventsUseCase`.
     - `GET /api/v1/stream`: Real-time Server-Sent Events (SSE) live feed via `StreamTelemetryEventsUseCase`.
     - `POST /api/v1/control/watch`: Start/stop stream via `ProcessTelemetryStreamUseCase`.

## Consequences
- `ed-telemetry` provides a full persistence and local HTTP/SSE API without adding third-party dependencies, adhering strictly to ADR 0020 anti-creep guardrails.
- Downstream tools can consume data via standard HTTP/SSE or directly from the SQLite database file in WAL mode.
