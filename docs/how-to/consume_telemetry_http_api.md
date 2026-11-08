---
title: "How to Consume the Telemetry HTTP & SSE API"
tags: ["how-to", "api", "rest", "sse", "streaming", "integration"]
created_at: "2026-10-25"
last_updated_at: "2026-11-08"
---

# How to Consume the Telemetry HTTP & SSE API

This practical runbook guides external client developers, dashboard builders, and overlay integrators through consuming live, real-time, and historical telemetry via the `ed-telemetry` HTTP REST and Server-Sent Events (SSE) server.

The API implements a dual-plane architecture ([ADR 0038](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0038_api_endpoint_taxonomy_dual_plane_model_and_state_heartbeat.md)):
1. **In-Memory State Plane:** Instantaneous, zero-DB state hydration (< 1ms) and push streams for real-time dashboards.
2. **Durable Log Plane:** Persistent SQLite storage in Write-Ahead Logging (WAL) mode for audit trails and historical queries.

---

## 1. Prerequisites & Health Check

Start the `ed-telemetry` daemon on the target host:
```bash
ed-telemetry serve --host 127.0.0.1 --port 8080
```

Verify service availability via the canonical system health endpoint:
```bash
curl http://127.0.0.1:8080/api/v1/system/health
```
Response:
```json
{"status": "ok", "service": "ed-telemetry"}
```

*(Note: Legacy alias `GET /api/v1/health` remains supported).*

---

## 2. Real-Time UI Synchronization Workflow

To eliminate stale data cycling, value flipping, and cold-start race conditions, downstream UIs should follow this three-phase lifecycle:

### Phase 1: Instant State Hydration (`GET /api/v1/state`)
Call `/api/v1/state` once upon client initialization to load all current telemetry without executing any SQLite queries:

```bash
curl -i http://127.0.0.1:8080/api/v1/state
```

Response headers and body:
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Telemetry-Source: memory-buffer
X-Telemetry-Plane: state
ETag: W/"14"
```
```json
{
  "state_sequence": 14,
  "timestamp": "2026-11-08T16:00:00+00:00",
  "active_journal": "Journal.2026-11-08T140000.01.log",
  "latest_journal_event": {
    "topic": "telemetry.journal",
    "timestamp": "2026-11-08T16:00:00+00:00",
    "payload_json": "{\"event\":\"FSDJump\",\"StarSystem\":\"Sol\"}"
  },
  "game_status": {
    "exists": true,
    "is_live_session": true,
    "target_path": "/path/to/Status.json",
    "timestamp": "2026-11-08T16:00:00+00:00",
    "raw_payload": "{\"event\":\"Status\",\"Flags\":16,\"Pips\":[4,4,4]}",
    "raw_hash": "365d6ebac12925c3"
  },
  "snapshots": {
    "Market": {
      "target_name": "Market.json",
      "exists": true,
      "is_live_session": true,
      "target_path": "/path/to/Market.json",
      "timestamp": "2026-11-08T16:00:00+00:00",
      "raw_payload": "{\"event\":\"Market\",\"MarketID\":1234}",
      "raw_hash": "065b4bcd26175059"
    }
  }
}
```

> [!TIP]
> The `is_live_session` boolean indicates whether a snapshot was updated during active gameplay (`true`) or preloaded cold from disk before gameplay began (`false`).

### Phase 2: Reactive Push Stream (`GET /api/v1/journal/stream`)
Subscribe to the continuous Server-Sent Events (SSE) stream for live updates:

```bash
curl -N http://127.0.0.1:8080/api/v1/journal/stream
```

JavaScript browser/desktop example:
```javascript
const eventSource = new EventSource("http://127.0.0.1:8080/api/v1/journal/stream");

eventSource.onmessage = (event) => {
  const telemetry = JSON.parse(event.data);
  if (telemetry.event === "connected") return;

  const payload = JSON.parse(telemetry.payload);
  switch (telemetry.topic) {
    case "telemetry.journal":
      console.log("Journal event:", payload);
      break;
    case "telemetry.status":
      console.log("Cockpit update:", payload);
      break;
    case "telemetry.snapshot":
      console.log("Snapshot update:", payload);
      break;
  }
};
```

*(Note: Legacy alias `GET /api/v1/stream` remains supported).*

### Phase 3: Drift Detection & Reconnection Heartbeat (`GET /api/v1/state/heartbeat`)
If the SSE connection drops or periodically every 5 seconds, poll the ultra-lightweight heartbeat (< 200 bytes) to detect state mutations:

```bash
curl http://127.0.0.1:8080/api/v1/state/heartbeat
```
Response:
```json
{
  "state_sequence": 14,
  "timestamp": "2026-11-08T16:00:05+00:00",
  "active_journal": "Journal.2026-11-08T140000.01.log",
  "latest_event_id": "c1f7b098-a3f4-41d7-b8d4-8d48e8a6042a",
  "status_hash": "365d6ebac12925c3",
  "snapshot_hashes": {
    "Market": "065b4bcd26175059"
  }
}
```

If `state_sequence` has advanced past the UI's local sequence, fetch `/api/v1/state` to resynchronize.

---

## 3. Dedicated Resource Endpoints

### Cockpit Status (`GET /api/v1/status`)
Retrieve the parsed player cockpit status (`Status.json`):
```bash
curl http://127.0.0.1:8080/api/v1/status
```

*(Note: Legacy alias `GET /api/v1/status/game` remains supported).*

### Auxiliary Snapshots (`GET /api/v1/snapshots` & `GET /api/v1/snapshots/{name}`)
Retrieve all snapshots or a specific file (`Market`, `Cargo`, `NavRoute`, `ModulesInfo`, `Outfitting`, `Shipyard`, `Backpack`, `ShipLocker`, `FCMaterials`):
```bash
# Retrieve all registered snapshots
curl http://127.0.0.1:8080/api/v1/snapshots

# Retrieve a specific snapshot
curl http://127.0.0.1:8080/api/v1/snapshots/market
curl http://127.0.0.1:8080/api/v1/snapshots/navroute
```

### Ingestion Watcher Status (`GET /api/v1/system/watcher`)
Inspect filesystem watcher operational metrics:
```bash
curl http://127.0.0.1:8080/api/v1/system/watcher
```
Response:
```json
{
  "is_active": true,
  "active_journal": "Journal.2026-11-08T140000.01.log",
  "monitored_directory": "/path/to/journal/directory"
}
```

---

## 4. Querying Historical Telemetry (`GET /api/v1/journal/query`)

Query persisted SQLite records with filtering:

```bash
# Query latest 10 events
curl "http://127.0.0.1:8080/api/v1/journal/query?limit=10"

# Filter by topic
curl "http://127.0.0.1:8080/api/v1/journal/query?topic=telemetry.journal&limit=50"

# Fetch events newer than sequential ID 42
curl "http://127.0.0.1:8080/api/v1/journal/query?since_id=42&limit=50"
```

*(Note: Legacy alias `GET /api/v1/events` remains supported).*

---

## 5. HTTP Caching via ETag (304 Not Modified)

State endpoints support weak ETag negotiation. Send the `If-None-Match` request header:

```bash
curl -i -H 'If-None-Match: W/"14"' http://127.0.0.1:8080/api/v1/state
```

Response:
```http
HTTP/1.1 304 Not Modified
ETag: W/"14"
X-Telemetry-Source: memory-buffer
X-Telemetry-Plane: state
```

---

## 6. RFC 7807 Problem Details Error Handling

All client and server errors return an `application/problem+json` payload:

```bash
curl http://127.0.0.1:8080/api/v1/snapshots/unknown_snapshot
```

Response (HTTP 404):
```json
{
  "type": "about:blank",
  "title": "Snapshot Not Found",
  "status": 404,
  "detail": "Auxiliary game snapshot 'unknown_snapshot' does not exist.",
  "instance": "/api/v1/snapshots/unknown_snapshot"
}
```
