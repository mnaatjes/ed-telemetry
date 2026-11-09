---
title: "HTTP REST & SSE API Reference"
tags: ["reference", "api", "rest", "sse", "endpoints", "http"]
created_at: "2026-10-25"
last_updated_at: "2026-11-08"
---

# HTTP REST & SSE API Reference

This technical reference specifies all REST and Server-Sent Events (SSE) endpoints exposed by `ed_telemetry.adapters.driving.api.server.HttpApiAdapter`.

The API implements a dual-plane architecture ([ADR 0038](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0038_api_endpoint_taxonomy_dual_plane_model_and_state_heartbeat.md)):
1. **In-Memory State Plane:** Instantaneous, zero-DB hydration and real-time pushes for live HUD/overlay consumers.
2. **Durable Log Plane:** Persistent SQLite storage for audit trails, historical event querying, and diagnostic replay.

---

## 1. Base URL & Protocol Standards

* **Base URL:** `http://<host>:<port>/api/v1` (Default: `http://127.0.0.1:8080/api/v1`).
* **Content Types:**
  * Successful JSON responses: `application/json`.
  * Error responses: `application/problem+json` ([RFC 7807](https://datatracker.ietf.org/doc/html/rfc7807)).
  * Live event stream: `text/event-stream`.
* **CORS:** Cross-Origin Resource Sharing is enabled on all endpoints (`Access-Control-Allow-Origin: *`).

### 1.1 Response Headers & Storage Transparency

All responses inject standard diagnostic headers establishing domain plane and storage origin:

| Header | Possible Values | Architectural Meaning |
| :--- | :--- | :--- |
| `X-Telemetry-Source` | `memory-buffer`, `sqlite-wal` | Indicates whether data originates from ephemeral in-memory state or durable SQLite WAL storage. |
| `X-Telemetry-Plane` | `state`, `status`, `snapshots`, `journal`, `system` | Declares the architectural resource plane of the invoked endpoint. |
| `ETag` | `W/"<state_sequence>"` or `W/"<raw_hash>"` | Weak ETag enabling HTTP `304 Not Modified` caching via `If-None-Match`. |

---

## 2. Canonical API Endpoints

### 2.1 State Hydration & Synchronization Plane

#### `GET /api/v1/state`
Retrieves consolidated instantaneous telemetry state across active journal tail, latest cockpit status, and all auxiliary snapshots.
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: state`
* **Caching:** Supports `If-None-Match` returning `304 Not Modified` when unchanged.
* **Legacy Alias (Deprecated):** `GET /api/v1/telemetry/head`
* **Status:** `200 OK` (or `503 Service Unavailable` if state port is not configured).
* **Response:**
  ```json
  {
    "state_sequence": 42,
    "timestamp": "2026-11-08T14:00:00+00:00",
    "active_journal": "Journal.2026-11-08T100000.01.log",
    "latest_journal_event": {
      "id": 42,
      "event_id": "c1f7b098-a3f4-41d7-b8d4-8d48e8a6042a",
      "topic": "telemetry.journal",
      "timestamp": "2026-11-08T14:00:00+00:00",
      "raw_hash": "a82f...",
      "payload_json": "{\"event\":\"FSDJump\",\"StarSystem\":\"Sol\"}",
      "created_at": "2026-11-08T14:00:01+00:00"
    },
    "game_status": {
      "exists": true,
      "is_live_session": true,
      "target_path": "/path/to/Status.json",
      "timestamp": "2026-11-08T14:00:00+00:00",
      "raw_payload": "{\"event\":\"Status\",\"Flags\":16842768}",
      "raw_hash": "365d6ebac12925c3"
    },
    "snapshots": {
      "Market": {
        "target_name": "Market.json",
        "exists": true,
        "is_live_session": true,
        "target_path": "/path/to/Market.json",
        "timestamp": "2026-11-08T14:00:00+00:00",
        "raw_payload": "{\"event\":\"Market\",\"MarketID\":1234}",
        "raw_hash": "065b4bcd26175059"
      }
    }
  }
  ```

#### `GET /api/v1/state/heartbeat`
Ultra-lightweight state synchronization heartbeat (< 200 bytes) providing atomic monotonic sequence counter and content hashes for delta polling and drift detection.
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: state`
* **Caching:** Supports `If-None-Match` returning `304 Not Modified`.
* **Status:** `200 OK`
* **Response:**
  ```json
  {
    "state_sequence": 42,
    "timestamp": "2026-11-08T14:00:00+00:00",
    "active_journal": "Journal.2026-11-08T100000.01.log",
    "latest_event_id": "c1f7b098-a3f4-41d7-b8d4-8d48e8a6042a",
    "status_hash": "365d6ebac12925c3",
    "snapshot_hashes": {
      "Market": "065b4bcd26175059",
      "Cargo": "8f3b..."
    }
  }
  ```

---

### 2.2 Cockpit Status Plane

#### `GET /api/v1/status`
Retrieves parsed content of the player cockpit status (`Status.json`).
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: status`
* **Legacy Alias (Deprecated):** `GET /api/v1/status/game`
* **Status:** `200 OK`
* **Response:**
  ```json
  {
    "exists": true,
    "is_live_session": true,
    "target_path": "/path/to/Status.json",
    "timestamp": "2026-10-25T16:00:00+00:00",
    "raw_payload": "{\"event\":\"Status\",\"Flags\":16842768}",
    "raw_hash": "365d6ebac12925c3"
  }
  ```

---

### 2.3 Auxiliary Snapshots Plane

#### `GET /api/v1/snapshots`
Retrieves all registered auxiliary game snapshot files in a consolidated dictionary.
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: snapshots`
* **Status:** `200 OK`

#### `GET /api/v1/snapshots/{name}`
Retrieves a specific auxiliary game snapshot file (`Market`, `Cargo`, `NavRoute`, `ModulesInfo`, `Outfitting`, `Shipyard`, `Backpack`, `ShipLocker`, `FCMaterials`).
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: snapshots`
* **Status:** `200 OK` (when found) or `404 Not Found` (Problem Details).
* **Response:**
  ```json
  {
    "target_name": "Market.json",
    "exists": true,
    "is_live_session": true,
    "target_path": "/path/to/Market.json",
    "timestamp": "2026-10-25T16:05:00+00:00",
    "raw_payload": "{\"event\":\"Market\",\"MarketID\":1234}",
    "raw_hash": "065b4bcd26175059"
  }
  ```

---

### 2.4 Journal Events Plane

#### `GET /api/v1/journal/latest`
Retrieves the most recent journal event from the active log tail.
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: journal`
* **Status:** `200 OK`

#### `GET /api/v1/journal/query`
Queries historical telemetry events persisted in SQLite.
* **Storage Source:** `X-Telemetry-Source: sqlite-wal`
* **Plane:** `X-Telemetry-Plane: journal`
* **Legacy Alias (Deprecated):** `GET /api/v1/events`
* **Query Parameters:**
  * `since_id` (integer, optional): Only events with `id > since_id`.
  * `topic` (string, optional): Filter by topic (`telemetry.journal`, `telemetry.status`, `telemetry.snapshot`, `telemetry.audit`).
  * `limit` (integer, optional, default: `100`, max: `500`): Maximum events returned.
  * `order` (string, optional, default: `asc`): Sort order by record ID (`asc` or `desc`).
* **Status:** `200 OK`
* **Response:** Array of `TelemetryRecordDTO` objects.

#### `GET /api/v1/journal/stream`
Continuous Server-Sent Events (SSE) feed transmitting live telemetry and file delta events.
* **Plane:** `X-Telemetry-Plane: journal`
* **Legacy Alias (Deprecated):** `GET /api/v1/stream`
* **Headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache`.
* **Payload Examples:**
  * **Initial Handshake:**
    ```text
    data: {"event":"connected"}
    ```
  * **Journal Line Append (`telemetry.journal`):**
    ```text
    data: {"topic": "telemetry.journal", "timestamp": "2026-10-25T16:00:00+00:00", "payload": "{\"event\":\"FSDJump\"}"}
    ```
  * **File Delta Notification (`telemetry.file_delta`):**
    ```text
    data: {"topic": "telemetry.file_delta", "target": "ModulesInfo.json", "action": "modified", "raw_hash": "43ef64b8e02f00b2", "timestamp": "2026-11-09T00:20:00+00:00"}
    ```

#### `GET /api/v1/journal/queue`
Retrieves and drains telemetry events currently buffered in the outbound in-memory ring queue.
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: journal`
* **Legacy Alias (Deprecated):** `GET /api/v1/events/buffer`
* **Query Parameters:**
  * `limit` (integer, optional, default: `100`, max: `500`): Maximum events to drain.
* **Status:** `200 OK`

---

### 2.5 System Plane

#### `GET /api/v1/system/health`
Health check endpoint reporting service operational status.
* **Plane:** `X-Telemetry-Plane: system`
* **Legacy Alias (Deprecated):** `GET /api/v1/health`
* **Status:** `200 OK`
* **Response:**
  ```json
  {"status": "ok", "service": "ed-telemetry"}
  ```

#### `GET /api/v1/system/watcher`
Reports ingestion watcher state, monitored directory path, and active journal file.
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: system`
* **Status:** `200 OK`
* **Response:**
  ```json
  {
    "is_active": true,
    "active_journal": "Journal.2026-10-25T140000.01.log",
    "monitored_directory": "/path/to/journal/directory"
  }
  ```

#### `GET /api/v1/system/logs`
Returns recent application log entries from the thread-safe in-memory ring buffer.
* **Storage Source:** `X-Telemetry-Source: memory-buffer`
* **Plane:** `X-Telemetry-Plane: system`
* **Legacy Alias (Deprecated):** `GET /api/v1/diagnostics/logs`
* **Query Parameters:**
  * `min_level` (string, optional): `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
  * `limit` (integer, optional, default: `100`, max: `500`): Maximum entries to return.
* **Status:** `200 OK`

#### `POST /api/v1/system/control`
Starts or stops background filesystem telemetry ingestion.
* **Plane:** `X-Telemetry-Plane: system`
* **Legacy Alias (Deprecated):** `POST /api/v1/control/watch`
* **Body:** `{"action": "start"}` or `{"action": "stop"}`.
* **Status:** `200 OK` on success, `400 Bad Request` on invalid action.
