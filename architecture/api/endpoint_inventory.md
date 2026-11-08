---
title: "HTTP & Streaming API Endpoint Analysis Inventory"
tags: ["architecture", "api", "inventory", "endpoints", "hexagonal"]
created_at: "2026-11-08"
last_updated_at: "2026-11-08"
---

# HTTP & Streaming API Endpoint Analysis Inventory

This document provides a comprehensive operational inventory of all HTTP REST and streaming endpoints hosted by `ed_telemetry.adapters.driving.api.server.HttpApiAdapter`.

---

## 1. Endpoint Classification & Source Analysis

| Endpoint URL | HTTP Method | Sourcefile Contents | Data-Source | Behavior(s) |
| :--- | :--- | :--- | :--- | :--- |
| `/api/v1/health` | `GET` | N/A | In-memory | Liveness check; returns service metadata without authentication. |
| `/api/v1/telemetry/head` | `GET` | `all` (`journal`, `status`, `snapshot`) | In-memory buffer + SQLite DB | Aggregates instantaneous consolidated state: active journal, latest persisted journal event from SQLite, latest `Status.json` state, and all auxiliary snapshot caches. |
| `/api/v1/diagnostics/logs` | `GET` | N/A | In-memory buffer | Queries in-memory diagnostic ring buffer; supports filtering by `min_level` (`DEBUG`, `INFO`, etc.) and `limit` (clamped 1–500). |
| `/api/v1/status` | `GET` | `journal` | In-memory | Returns telemetry watcher operational metrics: running status, active journal file, monitored directory path. |
| `/api/v1/control/watch` | `POST` | N/A | Reactor control loop | Triggers primary driving port `ProcessTelemetryStreamPort` to `start` or `stop` continuous ingestion threads. Returns RFC 7807 problem details on invalid action. |
| `/api/v1/status/game` | `GET` | `status` (`Status.json`) | In-memory buffer | Returns cached content and SHA-256 hash of active cockpit telemetry (`Status.json`). |
| `/api/v1/snapshots/{name}` | `GET` | `snapshot` (`Market`, `Cargo`, `NavRoute`, etc.) | In-memory buffer | Inspects auxiliary game state snapshot files. Returns 404 Problem Details if snapshot is unregistered or missing on disk. |
| `/api/v1/events` | `GET` | `journal` (and persisted snapshots) | SQLite DB | Queries persisted historical telemetry in WAL mode. Supports query filters: `topic`, `since_id`, `limit` (clamped 1–500), and `order` (`asc`/`desc`). |
| `/api/v1/events/buffer` | `GET` | `journal` | In-memory buffer | Drains and returns transient telemetry events currently queued in the outbound in-memory ring buffer. |
| `/api/v1/stream` | `GET` | `all` | In-memory stream generator | Long-lived Server-Sent Events (SSE) stream (`text/event-stream`). Emits initial connection heartbeat, enforces concurrent client limits (HTTP 429), and streams live journal/status/snapshot events. |

---

## 2. Ingestion & Persistence Topology

* **Direct Disk to Ring Buffer:** Active journal file lines, `Status.json`, and auxiliary snapshots (`Market.json`, etc.) are continuously monitored by the ingestion engine and cached in thread-safe memory buffers.
* **Asynchronous Persistence:** Journal events and snapshot mutations are indexed and written to SQLite in Write-Ahead Logging (WAL) mode for fast historical queries.
* **Zero-Copy / Memory-First Egress:** Fast path endpoints (`/telemetry/head`, `/status/game`, `/snapshots/{name}`, `/events/buffer`, `/stream`) read directly from memory representations, shielding SQLite from high-frequency polling.
