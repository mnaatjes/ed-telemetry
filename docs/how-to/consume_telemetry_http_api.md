---
title: "How to Consume the Telemetry HTTP & SSE API"
tags: ["how-to", "api", "rest", "sse", "streaming", "integration"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# How to Consume the Telemetry HTTP & SSE API

This practical runbook guides external client developers and dashboard integrators through consuming live and historical telemetry via the `ed-telemetry` HTTP REST and Server-Sent Events (SSE) server.

---

## 1. Prerequisites

Start the `ed-telemetry` daemon on the target host:
```bash
ed-telemetry serve --host 127.0.0.1 --port 8080
```

Verify service availability:
```bash
curl http://127.0.0.1:8080/api/v1/health
```
Response:
```json
{"status": "ok", "service": "ed-telemetry"}
```

---

## 2. Polling Game and Watcher Status

### Checking Ingestion Health
```bash
curl http://127.0.0.1:8080/api/v1/status
```
Response:
```json
{
  "is_active": true,
  "monitored_directory": "/path/to/Saved Games/.../Elite Dangerous",
  "active_journal": "Journal.2026-10-25T140000.01.log"
}
```

### Checking Player Cockpit Status
```bash
curl http://127.0.0.1:8080/api/v1/status/game
```
Response:
```json
{
  "exists": true,
  "target_path": "/path/to/Status.json",
  "timestamp": "2026-10-25T16:00:00+00:00",
  "raw_payload": "{\"event\":\"Status\",\"Flags\":16,\"Pips\":[4,4,4]}",
  "raw_hash": "365d6ebac12925c3"
}
```

### Retrieving Auxiliary Game Snapshots
Retrieve auxiliary game files (`Market.json`, `Cargo.json`, `NavRoute.json`, `ModulesInfo.json`, `Outfitting.json`, `Shipyard.json`):
```bash
curl http://127.0.0.1:8080/api/v1/snapshots/market
curl http://127.0.0.1:8080/api/v1/snapshots/navroute
```

---

## 3. Subscribing to Real-Time Telemetry (SSE)

The `/api/v1/stream` endpoint streams continuous JSON events as Server-Sent Events.

### Using `curl`
```bash
curl -N http://127.0.0.1:8080/api/v1/stream
```

Stream format:
```text
data: {"topic": "telemetry.journal", "timestamp": "2026-10-25T16:05:00+00:00", "payload": "{\"event\":\"FSDJump\",\"StarSystem\":\"Sol\"}"}

data: {"topic": "telemetry.status", "timestamp": "2026-10-25T16:05:01+00:00", "payload": "{\"event\":\"Status\",\"Flags\":16842768}"}
```

### Using JavaScript / Browser
```javascript
const eventSource = new EventSource("http://127.0.0.1:8080/api/v1/stream");

eventSource.onmessage = (event) => {
  const telemetry = JSON.parse(event.data);
  console.log(`[${telemetry.topic}] ${telemetry.timestamp}:`, JSON.parse(telemetry.payload));
};

eventSource.onerror = (err) => {
  console.error("Stream connection error:", err);
};
```

---

## 4. Querying Historical Telemetry Events

Query persisted SQLite records with filtering:

```bash
# Query latest 10 events
curl "http://127.0.0.1:8080/api/v1/events?limit=10"

# Filter by topic
curl "http://127.0.0.1:8080/api/v1/events?topic=telemetry.journal&limit=50"

# Fetch events newer than ID 42
curl "http://127.0.0.1:8080/api/v1/events?since_id=42&limit=50"
```

---

## 5. Handling Errors (RFC 7807 Problem Details)

All client and server errors return an `application/problem+json` response:

```bash
curl http://127.0.0.1:8080/api/v1/snapshots/unknown_snapshot
```

Error response (HTTP 404):
```json
{
  "type": "about:blank",
  "title": "Snapshot Not Found",
  "status": 404,
  "detail": "Auxiliary game snapshot 'unknown_snapshot.json' does not exist.",
  "instance": "/api/v1/snapshots/unknown_snapshot"
}
```
