---
title: "ADR 0023: HTTP and Streaming API Endpoint Specifications"
tags: ["adr", "api", "rest", "sse", "openapi", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0023: HTTP and Streaming API Endpoint Specifications

## Status
Accepted

## Context
ADR 0022 established the zero-dependency `HttpApiAdapter` and SQLite WAL persistence. To enable downstream companion clients (e.g., local web dashboards, Discord bots, overlay tools, EDAstro/EDDN forwarders) to integrate reliably and predictably, the API contract must be formally specified, versioned, and standardized across HTTP and Server-Sent Events (SSE).

Key requirements:
1. Complete OpenAPI 3.1 contract authored under `architecture/api/openapi.yaml`.
2. Standardized error reporting conforming to RFC 7807 (Problem Details for HTTP APIs).
3. Explicit URI namespace under `/api/v1/` distinguishing health, operational watcher control, live event streaming, historical queries, and auxiliary snapshot reads.
4. Strict zero-dependency implementation using Python's standard library (`http.server`, `threading`, `json`, `urllib`).

## Decision

1. **Standardized Route Hierarchy (`/api/v1/`):**
   - **System & Health:**
     - `GET /api/v1/health` — Service liveness and basic telemetry status.
     - `GET /api/v1/status` — Watcher thread state, polling interval, and backpressure metrics.
     - `POST /api/v1/control/watch` — Dynamic lifecycle management (`action: "start" | "stop"`).
   - **Game State Snapshots:**
     - `GET /api/v1/status/game` — Latest `Status.json` telemetry state (GUI focus, pips, coordinates, flags).
     - `GET /api/v1/snapshots/{name}` — Auxiliary game snapshot files (`Market`, `Cargo`, `NavRoute`, `Outfitting`, `Shipyard`, `ModulesInfo`).
   - **Event Consumption & Querying:**
     - `GET /api/v1/events` — Filtered historical query against SQLite WAL with `topic`, `since_id`, and `limit`.
     - `GET /api/v1/events/buffer` — Batch draining from the in-memory ring buffer.
     - `GET /api/v1/stream` — Real-time live feed over Server-Sent Events (`text/event-stream`).

2. **Error Responses (RFC 7807):**
   - Standardize all error payloads with `Content-Type: application/problem+json` containing `type`, `title`, `status`, `detail`, and `instance`.

3. **Streaming Protocol:**
   - Use standard SSE (`text/event-stream`) for `/api/v1/stream`, sending an initial heartbeat `{ "event": "connected" }` followed by JSON-encoded telemetry events with `data: ...\n\n`.

4. **Zero-Dependency Guardrail:**
   - Adhere strictly to ADR 0020; the HTTP server implementation must not pull in FastAPI, Flask, Starlette, or external WSGI/ASGI servers.

## Consequences
- Downstream tools receive a deterministic, versioned, machine-readable interface contract in OpenAPI 3.1.
- All routes map directly to driving port protocols without leaking internal storage or threading mechanics.
