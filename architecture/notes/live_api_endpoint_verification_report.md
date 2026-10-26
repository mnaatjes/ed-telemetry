---
title: "Live HTTP REST & SSE API Endpoint Verification Report"
tags: ["api", "verification", "testing", "http", "sse", "report"]
created_at: "2026-10-26"
last_updated_at: "2026-10-26"
---

# Live HTTP REST & SSE API Endpoint Verification Report

This document records the systematic verification of all HTTP REST and Server-Sent Events (SSE) endpoints exposed by the running `ed-telemetry` daemon on `http://michael-desktop.lan:8080/api/v1` against the specification in [`architecture/api/openapi.yaml`](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/api/openapi.yaml).

---

## 1. Environment & Target Context

* **Host:** `michael-desktop.lan` (`192.168.1.214:8080`)
* **Client:** Local LAN host (`192.168.1.106`)
* **Daemon Version:** `v0.5.0`
* **Operating System Target:** Linux Steam Proton (Elite Dangerous Odyssey active)
* **API Specification:** [`architecture/api/openapi.yaml`](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/api/openapi.yaml) (OpenAPI 3.1.0)

---

## 2. Test Execution & Result Matrix

| # | Endpoint / Method | Expected Status | Actual Status | Content-Type | Verification Result |
| :- | :--- | :-: | :-: | :--- | :-: |
| 1 | `GET /api/v1/health` | `200` | `200 OK` | `application/json` | **PASS** |
| 2 | `GET /api/v1/status` | `200` | `200 OK` | `application/json` | **PASS** |
| 3 | `GET /api/v1/status/game` | `200` | `200 OK` | `application/json` | **PASS** |
| 4 | `GET /api/v1/snapshots/Market` | `200` | `200 OK` | `application/json` | **PASS** |
| 5 | `GET /api/v1/snapshots/nonexistent` | `404` | `404 Not Found` | `application/problem+json` | **PASS** |
| 6 | `GET /api/v1/events?limit=2` | `200` | `200 OK` | `application/json` | **PASS** |
| 7 | `GET /api/v1/events/buffer?limit=2` | `200` | `200 OK` | `application/json` | **PASS** |
| 8 | `GET /api/v1/diagnostics/logs` | `200` | `200 OK` | `application/json` | **PASS** |
| 9 | `GET /api/v1/stream` (SSE) | `200` | `200 OK` | `text/event-stream` | **PASS** |
| 10 | `POST /api/v1/control/watch` (invalid) | `400` | `400 Bad Request` | `application/problem+json` | **PASS** |
| 11 | `GET /api/v1/unknown_resource` | `404` | `404 Not Found` | `application/problem+json` | **PASS** |

---

## 3. Systematic Verification Walkthrough

### 3.1 Liveness Probe (`GET /api/v1/health`)
* **Request:** `curl -s -i http://michael-desktop.lan:8080/api/v1/health`
* **Response Status:** `HTTP/1.0 200 OK`
* **Response Payload:**
  ```json
  {"status": "ok", "service": "ed-telemetry"}
  ```
* **Findings:** CORS headers present (`Access-Control-Allow-Origin: *`). Conforms to OpenAPI schema.

---

### 3.2 Ingestion & Watcher Status (`GET /api/v1/status`)
* **Request:** `curl -s -i http://michael-desktop.lan:8080/api/v1/status`
* **Response Status:** `HTTP/1.0 200 OK`
* **Response Payload:**
  ```json
  {
    "is_active": true,
    "active_journal": "Journal.2026-10-25T195345.01.log",
    "monitored_directory": "/home/michael/.steam/debian-installation/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous"
  }
  ```
* **Findings:** `is_active: true` confirms the daemon is actively listening. Active journal and Proton path resolved dynamically.

---

### 3.3 Cockpit Telemetry (`GET /api/v1/status/game`)
* **Request:** `curl -s -i http://michael-desktop.lan:8080/api/v1/status/game`
* **Response Status:** `HTTP/1.0 200 OK`
* **Response Payload:**
  ```json
  {
    "exists": true,
    "target_path": "/home/michael/.steam/debian-installation/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous/Status.json",
    "timestamp": "2026-10-26T00:14:41.943539+00:00",
    "raw_payload": "{ \"timestamp\":\"2026-10-25T23:56:01Z\", \"event\":\"Status\", \"Flags\":151060493, \"Flags2\":0, \"Pips\":[3,7,2], \"FireGroup\":0, \"GuiFocus\":0, \"Fuel\":{ \"FuelMain\":16.000000, \"FuelReservoir\":0.490000 }, \"Cargo\":0.000000, \"LegalState\":\"Clean\", \"Balance\":5235083083 }",
    "raw_hash": "f8c0ca75f4f6700a"
  }
  ```
* **Findings:** Live cockpit snapshot returned with bitmasks, pips (`[3, 7, 2]`), fuel reservoir, balance, and content hash.

---

### 3.4 Auxiliary Snapshot Resolution (`GET /api/v1/snapshots/Market`)
* **Request:** `curl -s -i http://michael-desktop.lan:8080/api/v1/snapshots/Market`
* **Response Status:** `HTTP/1.0 200 OK`
* **Response Payload:**
  ```json
  {
    "target_name": "Market.json",
    "exists": true,
    "target_path": "/home/michael/.steam/debian-installation/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous/Market.json",
    "timestamp": "2026-10-26T00:14:46.294685+00:00",
    "raw_payload": "{ \"timestamp\":\"2026-10-25T18:29:19Z\", \"event\":\"Market\", \"MarketID\":3715110400, ... }",
    "raw_hash": "6c7fd9c93e9c9cee"
  }
  ```
* **Findings:** Case-normalized resolution automatically appends `.json` and extracts data from disk.

---

### 3.5 Snapshot Missing Error (`GET /api/v1/snapshots/nonexistent`)
* **Request:** `curl -s -i http://michael-desktop.lan:8080/api/v1/snapshots/nonexistent`
* **Response Status:** `HTTP/1.0 404 Not Found`
* **Content-Type:** `application/problem+json`
* **Response Payload:**
  ```json
  {
    "type": "about:blank",
    "title": "Snapshot Not Found",
    "status": 404,
    "detail": "Auxiliary game snapshot 'nonexistent.json' is not recognized or does not exist.",
    "instance": "/api/v1/snapshots/nonexistent"
  }
  ```
* **Findings:** RFC 7807 problem details error handling verified.

---

### 3.6 Historical Events Query (`GET /api/v1/events?limit=2`)
* **Request:** `curl -s -i "http://michael-desktop.lan:8080/api/v1/events?limit=2"`
* **Response Status:** `HTTP/1.0 200 OK`
* **Response Payload:** Returns array of records from SQLite with sequential `id`, `event_id`, `topic`, `payload_json`, and `created_at`.

---

### 3.7 In-Memory Buffered Queue Drain (`GET /api/v1/events/buffer?limit=2`)
* **Request:** `curl -s -i "http://michael-desktop.lan:8080/api/v1/events/buffer?limit=2"`
* **Response Status:** `HTTP/1.0 200 OK`
* **Response Payload:**
  ```json
  {"events": [], "remaining_count": 0, "dropped_count": 0}
  ```
* **Findings:** Correctly queries in-memory buffer queue adapter.

---

### 3.8 Diagnostic Log Ring Buffer (`GET /api/v1/diagnostics/logs`)
* **Request:** `curl -s -i "http://michael-desktop.lan:8080/api/v1/diagnostics/logs?limit=2"`
* **Response Status:** `HTTP/1.0 200 OK`
* **Response Payload:**
  ```json
  {"records": [], "total_retained": 0}
  ```
* **Findings:** Successfully queries `DiagnosticLogBuffer` on the running daemon.

---

### 3.9 Live Server-Sent Events Feed (`GET /api/v1/stream`)
* **Request:** `timeout 3 curl -N -s http://michael-desktop.lan:8080/api/v1/stream`
* **Response Status:** `HTTP/1.0 200 OK`
* **Content-Type:** `text/event-stream`
* **Response Stream:**
  ```text
  data: {"event":"connected"}
  ```
* **Findings:** Initial connected heartbeat received; SSE keep-alive connection holds open as specified.

---

### 3.10 Control POST Validation (`POST /api/v1/control/watch`)
* **Request:** `curl -s -i -X POST http://michael-desktop.lan:8080/api/v1/control/watch -H "Content-Type: application/json" -d '{"action":"invalid"}'`
* **Response Status:** `HTTP/1.0 400 Bad Request`
* **Content-Type:** `application/problem+json`
* **Response Payload:**
  ```json
  {
    "type": "about:blank",
    "title": "Bad Request",
    "status": 400,
    "detail": "Unknown control action: 'invalid'. Expected 'start' or 'stop'.",
    "instance": "/api/v1/control/watch"
  }
  ```
* **Findings:** Schema validation and RFC 7807 rejection for illegal control verbs confirmed.

---

### 3.11 Unrecognized Route (`GET /api/v1/unknown_resource`)
* **Request:** `curl -s -i http://michael-desktop.lan:8080/api/v1/unknown_resource`
* **Response Status:** `HTTP/1.0 404 Not Found`
* **Content-Type:** `application/problem+json`
* **Response Payload:**
  ```json
  {
    "type": "about:blank",
    "title": "Not Found",
    "status": 404,
    "detail": "Resource '/api/v1/unknown_resource' does not exist on this server.",
    "instance": "/api/v1/unknown_resource"
  }
  ```
* **Findings:** Default routing fallback emits standardized RFC 7807 payload.
