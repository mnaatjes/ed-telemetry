---
title: "HTTP REST & SSE API Reference"
tags: ["reference", "api", "rest", "sse", "endpoints", "http"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# HTTP REST & SSE API Reference

This technical reference specifies all REST and Server-Sent Events (SSE) endpoints exposed by `ed_telemetry.adapters.driving.api.server.HttpApiAdapter`.

---

## 1. Base URL & Protocol Standards

* **Base URL:** `http://<host>:<port>/api/v1` (Default: `http://127.0.0.1:8080/api/v1`).
* **Content Types:**
  * Successful JSON responses: `application/json`.
  * Error responses: `application/problem+json` ([RFC 7807](https://datatracker.ietf.org/doc/html/rfc7807)).
  * Live event stream: `text/event-stream`.
* **CORS:** Cross-Origin Resource Sharing is enabled on all endpoints (`Access-Control-Allow-Origin: *`).

---

## 2. API Endpoints

### 2.1 `GET /api/v1/health`
Health check endpoint reporting service operational status.
* **Status:** `200 OK`
* **Response:**
  ```json
  {"status": "ok", "service": "ed-telemetry"}
  ```

---

### 2.2 `GET /api/v1/status`
Reports ingestion watcher state, monitored directory path, and active journal file.
* **Status:** `200 OK`
* **Response:**
  ```json
  {
    "is_active": true,
    "monitored_directory": "/path/to/journal/directory",
    "active_journal": "Journal.2026-10-25T140000.01.log"
  }
  ```

---

### 2.3 `GET /api/v1/status/game`
Retrieves the parsed content of the active player cockpit status (`Status.json`).
* **Status:** `200 OK`
* **Response:**
  ```json
  {
    "exists": true,
    "target_path": "/path/to/Status.json",
    "timestamp": "2026-10-25T16:00:00+00:00",
    "raw_payload": "{\"event\":\"Status\",\"Flags\":16842768}",
    "raw_hash": "365d6ebac12925c3"
  }
  ```

---

### 2.4 `GET /api/v1/snapshots/{name}`
Retrieves a specific auxiliary game snapshot file (`market`, `cargo`, `navroute`, `modulesinfo`, `outfitting`, `shipyard`).
* **Status:** `200 OK` (when found) or `404 Not Found` (Problem Details).
* **Response:**
  ```json
  {
    "target_name": "Market.json",
    "exists": true,
    "target_path": "/path/to/Market.json",
    "timestamp": "2026-10-25T16:05:00+00:00",
    "raw_payload": "{\"event\":\"Market\",\"MarketID\":1234}",
    "raw_hash": "065b4bcd26175059"
  }
  ```

---

### 2.5 `GET /api/v1/events`
Queries historical telemetry events persisted in SQLite.
* **Query Parameters:**
  * `since_id` (integer, optional): Only events with `id > since_id`.
  * `topic` (string, optional): Filter by topic (`telemetry.journal`, `telemetry.status`, `telemetry.snapshot`, `telemetry.audit`).
  * `limit` (integer, optional, default: `100`): Maximum events returned.
* **Status:** `200 OK`
* **Response:** Array of `TelemetryRecordDTO` objects.

---

### 2.6 `GET /api/v1/stream`
Continuous Server-Sent Events (SSE) feed transmitting live telemetry and audit events.
* **Headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache`.
* **Payload:**
  ```text
  data: {"topic": "telemetry.journal", "timestamp": "2026-10-25T16:00:00+00:00", "payload": "{\"event\":\"FSDJump\"}"}
  ```

---

### 2.7 `GET /api/v1/diagnostics/logs`
Returns recent application log entries from the thread-safe in-memory ring buffer.
* **Query Parameters:**
  * `min_level` (string, optional): `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
  * `limit` (integer, optional, default: `100`): Maximum entries to return.
* **Status:** `200 OK`
* **Response:**
  ```json
  {
    "records": [
      {
        "timestamp": "2026-10-25T16:00:00+00:00",
        "level": "INFO",
        "logger_name": "ed_telemetry.adapters.driven.watcher",
        "message": "Watcher started on /path/to/journals"
      }
    ],
    "total_retained": 1
  }
  ```

---

### 2.8 `POST /api/v1/control/watch`
Starts or stops background filesystem telemetry ingestion.
* **Body:** `{"action": "start"}` or `{"action": "stop"}`.
* **Status:** `200 OK` on success, `400 Bad Request` on invalid action.
