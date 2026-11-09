---
title: "SDD-035: Journal Plane Isolation and Events Plane Implementation"
status: "implemented"
date: "2026-11-09"
author: "Architecture Team"
implements:
  - "architecture/adr/0041_journal_plane_isolation_and_events_plane_taxonomy.md"
tags: ["sdd", "api", "journal", "events", "persistence", "taxonomy"]
---

# SDD-035: Journal Plane Isolation and Events Plane Implementation

## 1. Overview & System Context

This Software Design Document specifies the technical implementation details for isolating the **Journal Plane** (`/api/v1/journal/*`) from the **Events Plane** (`/api/v1/events/*`), enforcing the architectural contracts established in ADR 0041.

---

## 2. Detailed Technical Design

### 2.1 Persistence Layer Query Protocol (`TelemetryQueryDTO` & `SqliteEventStoreAdapter`)

To prevent non-journal system records (e.g., `telemetry.file_delta`) from polluting journal queries, `TelemetryQueryDTO` is extended with an optional boolean flag:

```python
@dataclass(frozen=True, slots=True)
class TelemetryQueryDTO(DataTransferObject):
    since_id: int | None = None
    topic: str | None = None
    limit: int = 100
    order: str = "asc"
    exclude_internal_topics: bool = False
```

When `exclude_internal_topics` is `True`, `SqliteEventStoreAdapter.find_events()` appends the following predicate:
```sql
topic NOT LIKE 'telemetry.%'
```

### 2.2 HTTP Server Routing & Header Injection

In `HttpApiAdapter.do_GET()`:

1. **`/api/v1/journal/events` (and deprecated alias `/api/v1/journal/query`):**
   - Instantiates `TelemetryQueryDTO` with `exclude_internal_topics=True`.
   - Injects `X-Telemetry-Plane: journal`.
   - Injects `X-Telemetry-Source: sqlite-wal`.

2. **`/api/v1/events/query` (and alias `/api/v1/events`):**
   - Instantiates `TelemetryQueryDTO` with `exclude_internal_topics=False`.
   - Injects `X-Telemetry-Plane: events`.
   - Injects `X-Telemetry-Source: sqlite-wal`.

3. **`/api/v1/events/queue` (and deprecated alias `/api/v1/journal/queue`, legacy `/api/v1/events/buffer`):**
   - Injects `X-Telemetry-Plane: events`.
   - Injects `X-Telemetry-Source: memory-buffer`.

4. **`/api/v1/events/stream` (and deprecated alias `/api/v1/journal/stream`, legacy `/api/v1/stream`):**
   - SSE transmitter.
   - Injects `X-Telemetry-Plane: events`.
   - Injects `X-Telemetry-Source: memory-buffer`.

---

## 3. Verification & Compliance Gates

1. Architectural test `test_api_standards.py`:
   - Updated `CANONICAL_ROUTE_PATTERN` to accept `/api/v1/events/(query|queue|stream)` and `/api/v1/journal/(latest|events)`.
   - Updated `DEPRECATED_LEGACY_ROUTES` to include `/api/v1/journal/query`, `/api/v1/journal/queue`, and `/api/v1/journal/stream`.
2. Unit test `test_sqlite_adapter.py`:
   - Validates that `exclude_internal_topics=True` suppresses `telemetry.file_delta` records.
3. Unit test `test_http_api.py`:
   - Validates plane headers and response statuses for all canonical and aliased routes.
