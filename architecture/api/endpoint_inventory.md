---
title: "HTTP & Streaming API Endpoint Analysis Inventory"
tags: ["architecture", "api", "inventory", "endpoints", "hexagonal"]
created_at: "2026-11-08"
last_updated_at: "2026-11-08"
---

# HTTP & Streaming API Endpoint Analysis Inventory

This document provides a comprehensive operational inventory of all HTTP REST and streaming endpoints hosted by `ed_telemetry.adapters.driving.api.server.HttpApiAdapter`.

The architecture implements a dual-plane model decoupling the in-memory state synchronization plane (for real-time dashboards and overlays) from the durable SQLite log plane (for historical queries and audit replay) as formalized in [ADR 0038](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0038_api_endpoint_taxonomy_dual_plane_model_and_state_heartbeat.md).

---

## 1. Canonical Endpoint Classification & Storage Source Inventory

| Endpoint URL | HTTP Method | Architectural Plane | Storage Source | RFC 7807 Errors | Description / Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/v1/state` | `GET` | `state` | `memory-buffer` | `503` | Consolidated instantaneous state hydration (Zero-DB tail reader + cockpit status + all snapshots). Injects weak ETag `W/"<seq>"`; supports `304 Not Modified`. |
| `/api/v1/state/heartbeat` | `GET` | `state` | `memory-buffer` | N/A | Ultra-lightweight state delta heartbeat (< 200 bytes) with atomic `state_sequence` counter and content hashes for drift detection. Supports `304 Not Modified`. |
| `/api/v1/status` | `GET` | `status` | `memory-buffer` | `503` | Real-time cockpit telemetry (`Status.json`) content, `is_live_session` freshness flag, and SHA-256 hash. (Falls back to watcher status if game status port unconfigured). |
| `/api/v1/snapshots` | `GET` | `snapshots` | `memory-buffer` | N/A | Dictionary of all 9 registered auxiliary snapshots (`Market`, `Cargo`, `NavRoute`, `ModulesInfo`, `Outfitting`, `Shipyard`, `Backpack`, `ShipLocker`, `FCMaterials`). |
| `/api/v1/snapshots/{name}` | `GET` | `snapshots` | `memory-buffer` | `404` | Single auxiliary game snapshot payload, `is_live_session` freshness indicator, and SHA-256 hash. |
| `/api/v1/journal/latest` | `GET` | `journal` | `memory-buffer` | N/A | Most recent journal event read directly from the active log tail buffer. |
| `/api/v1/journal/query` | `GET` | `journal` | `sqlite-wal` | `400` | Historical persisted telemetry query across SQLite WAL index (`since_id`, `topic`, `limit`, `order`). |
| `/api/v1/journal/stream` | `GET` | `journal` | `memory-buffer` | `429` | Server-Sent Events (SSE) live push stream for journal lines (`telemetry.journal`) and file delta events (`telemetry.file_delta`). Enforces connection tracker guardrail (`429 Too Many Requests`). |
| `/api/v1/journal/queue` | `GET` | `journal` | `memory-buffer` | N/A | Drains outbound in-memory ring queue buffer. |
| `/api/v1/system/health` | `GET` | `system` | `memory-buffer` | N/A | Unauthenticated service liveness check (`{"status": "ok", "service": "ed-telemetry"}`). |
| `/api/v1/system/watcher` | `GET` | `system` | `memory-buffer` | `503` | Ingestion watcher operational metrics (active journal file, monitored directory, active status). |
| `/api/v1/system/logs` | `GET` | `system` | `memory-buffer` | N/A | Queries thread-safe in-memory diagnostic log ring buffer (`min_level`, `limit`). |
| `/api/v1/system/control` | `POST` | `system` | `memory-buffer` | `400` | Controls filesystem watcher reactor lifecycle (`{"action": "start" \| "stop"}`). |

---

## 2. Deprecated Legacy Route Aliases

For seamless backward compatibility with v0.x clients, all legacy routes are maintained as exact dispatch aliases:

| Legacy Route (Deprecated) | Canonical Equivalent | Redirection / Dispatch Behavior |
| :--- | :--- | :--- |
| `GET /api/v1/telemetry/head` | `GET /api/v1/state` | Directly dispatches to state hydration handler with zero DB calls. |
| `GET /api/v1/status/game` | `GET /api/v1/status` | Dispatches to cockpit status handler. |
| `GET /api/v1/events` | `GET /api/v1/journal/query` | Dispatches to SQLite historical query handler. |
| `GET /api/v1/events/buffer` | `GET /api/v1/journal/queue` | Dispatches to in-memory queue drain handler. |
| `GET /api/v1/stream` | `GET /api/v1/journal/stream` | Dispatches to SSE streaming handler. |
| `GET /api/v1/health` | `GET /api/v1/system/health` | Dispatches to system health check. |
| `GET /api/v1/diagnostics/logs` | `GET /api/v1/system/logs` | Dispatches to diagnostic logs handler. |
| `POST /api/v1/control/watch` | `POST /api/v1/system/control` | Dispatches to system control handler. |

---

## 3. Storage Transparency & Metadata Invariants

### 3.1 HTTP Diagnostic Response Headers
Every response from `HttpApiAdapter` injects two mandatory transparency headers plus optional caching negotiation:

| Header | Example Value | Architectural Meaning |
| :--- | :--- | :--- |
| `X-Telemetry-Source` | `memory-buffer` \| `sqlite-wal` | Informs callers whether payload was generated from ephemeral RAM cache or durable SQLite storage. |
| `X-Telemetry-Plane` | `state` \| `status` \| `snapshots` \| `journal` \| `system` | Declares the architectural resource plane of the endpoint. |
| `ETag` | `W/"42"` \| `W/"365d6ebac12925c3"` | Weak entity tag enabling conditional caching via `If-None-Match` (returns `304 Not Modified`). |

### 3.2 Payload Metadata Properties
The core data transfer objects expose standard telemetry metadata:

| Property | Location | Type | Semantic Description |
| :--- | :--- | :--- | :--- |
| `state_sequence` | `/state`, `/state/heartbeat` | `int64` | Monotonically increasing atomic sequence counter incremented on every journal event or snapshot rewrite. |
| `is_live_session` | `/status`, `/snapshots/*`, `/state` | `bool` | Freshness indicator: `true` if file modified during the active daemon session; `false` if preloaded cold from disk. |
| `raw_hash` | `/status`, `/snapshots/*`, `/state` | `str` (SHA-256) | Content hash for change detection without parsing deep JSON trees. |
| `timestamp` | All DTOs | `str` (ISO 8601 UTC) | File modification time or game event creation timestamp. |
