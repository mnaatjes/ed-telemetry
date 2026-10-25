---
title: "SDD-021: HTTP and Streaming API Endpoint Specifications"
tags: ["sdd", "api", "rest", "sse", "openapi", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-021: HTTP and Streaming API Endpoint Specifications

## 1. Executive Summary
This design document defines the concrete request/response contracts, URI routing table, RFC 7807 error schema, and Server-Sent Events (SSE) streaming semantics for the `HttpApiAdapter` driving adapter.

## 2. API Routing Table

| Method | Path | Use Case Port | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | (Static / Internal) | Liveness probe returning service metadata. |
| `GET` | `/api/v1/status` | `GetWatcherStatusPort` | Ingestion watcher thread status and metrics. |
| `POST` | `/api/v1/control/watch` | `ProcessTelemetryStreamPort` | Dynamic start or stop of telemetry stream ingestion. |
| `GET` | `/api/v1/status/game` | `GetLatestGameStatusPort` | Live Elite Dangerous game state from `Status.json`. |
| `GET` | `/api/v1/snapshots/{name}` | `GetAuxiliarySnapshotPort` | Auxiliary game snapshots (e.g. `Market`, `Cargo`). |
| `GET` | `/api/v1/events` | `FindTelemetryEventsPort` | Historical indexed query against SQLite database. |
| `GET` | `/api/v1/events/buffer` | `GetTelemetryEventsPort` | Read/drain buffered events from in-memory ring buffer. |
| `GET` | `/api/v1/stream` | `GetTelemetryStreamPort` | Server-Sent Events live stream (`text/event-stream`). |

## 3. RFC 7807 Problem Details Schema

All HTTP 4xx and 5xx responses must return `Content-Type: application/problem+json` matching:

```json
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "Invalid JSON body provided.",
  "instance": "/api/v1/control/watch"
}
```

## 4. Snapshot File Resolution (`/api/v1/snapshots/{name}`)
The `name` parameter accepts case-insensitive snapshot names with or without the `.json` extension:
- `market` -> resolves to `Market.json`
- `cargo` -> resolves to `Cargo.json`
- `navroute` -> resolves to `NavRoute.json`
- `outfitting` -> resolves to `Outfitting.json`
- `shipyard` -> resolves to `Shipyard.json`
- `modulesinfo` -> resolves to `ModulesInfo.json`

If the snapshot does not exist on disk or has no content, return HTTP 404 with Problem Details.

## 5. SSE Streaming Protocol (`/api/v1/stream`)
1. Client connects via HTTP GET with `Accept: text/event-stream`.
2. Server responds with HTTP 200, `Content-Type: text/event-stream`, `Cache-Control: no-cache`.
3. Initial connection event:
   ```
   data: {"event":"connected"}

   ```
4. Subsequent event dispatch:
   ```
   data: {"topic":"telemetry.journal","timestamp":"2026-10-25T12:00:00Z","payload":"{\"event\":\"FSDJump\"}"}

   ```
