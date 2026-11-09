---
title: "ADR 0041: Journal Plane Isolation and Events Plane Taxonomy Realignment"
status: "accepted"
date: "2026-11-09"
deciders: ["Architecture Team", "Integration Working Group"]
consulted: ["Operator Manual Governance", "API Standards Working Group"]
informed: ["Fleet Client Developers", "Daemon Maintainers"]
tags: ["api", "journal", "events", "taxonomy", "persistence", "sse", "adr"]
---

# ADR 0041: Journal Plane Isolation and Events Plane Taxonomy Realignment

## Context and Problem Statement

In ADR 0038, `ed-telemetry` adopted a resource-first canonical endpoint taxonomy dividing daemon endpoints into planes: `state`, `status`, `snapshots`, `journal`, and `system`.

However, the SQLite persistence store (`telemetry_events`) and egress transmission queue (`buffered_queue`) capture **all** ingestion events—including both Frontier `Journal.*.log` records (e.g. `FSDJump`, `Location`) and internal daemon/watcher lifecycle notifications (such as `telemetry.file_delta` introduced in ADR 0039 and ADR 0040).

By routing generic SQLite database queries, in-memory queue drains, and unified SSE streaming under `/api/v1/journal/*` (`/api/v1/journal/query`, `/api/v1/journal/queue`, `/api/v1/journal/stream`):
1. **Domain Language Contamination:** Querying `/api/v1/journal/query` without query arguments returned `telemetry.file_delta` events for companion files (`Status.json`, `Cargo.json`, etc.). Calling something "journal" when it contains non-journal data violates ubiquitous language and domain purity.
2. **Ambiguous Plane Headers:** The server attached `X-Telemetry-Plane: journal` to endpoints that multiplex file watcher deltas and general system events.
3. **Queue and Stream Overloading:** Draining `/api/v1/journal/queue` and listening to `/api/v1/journal/stream` drained and streamed generic telemetry payloads rather than solely journal events.

A strict boundary separation is required to guarantee that `/journal/*` endpoints strictly and exclusively serve Frontier `Journal.*.log` data, while general event queries, queue drains, and multi-topic streaming are reassigned to the **Events Plane** (`/events/*`).

---

## Decision Drivers

* **Ubiquitous Language & Domain Boundary Purity:** "Journal" in `ed-telemetry` must strictly and exclusively designate Frontier Developments `Journal.*.log` files and parsed journal JSONL records.
* **Predictable Query Semantics:** Querying journal endpoints must never return internal filesystem audit deltas (`telemetry.file_delta`) or non-journal metadata.
* **Unified Event Plane Visibility:** Consumers needing access to the entire ingestion history (game events plus companion snapshot lifecycle changes) require a dedicated, explicit plane (`/api/v1/events/*`).
* **Zero Disruption / 100% Backward Compatibility:** Preserve existing legacy endpoints and previous ADR 0038 routes as compatibility aliases until v1.0.0.

---

## Considered Options

* **Option 1 (Status Quo):** Keep all queries, queues, and streams under `/api/v1/journal/*` and require clients to pass `?topic=` filters.
  * *Con:* Severely violates domain boundaries; default queries return non-journal records.
* **Option 2 (Plane Realignment & Strict SQL Isolation - Selected):**
  * Quarantines the **Journal Plane** (`/api/v1/journal/*`) strictly to Frontier journal records. Make `/api/v1/journal/events` enforce `WHERE topic NOT LIKE 'telemetry.%'`.
  * Establish the **Events Plane** (`/api/v1/events/*`) for cross-cutting queries (`/api/v1/events/query` or `/api/v1/events`), queue draining (`/api/v1/events/queue`), and real-time streaming (`/api/v1/events/stream`).

---

## Decision Outcome

Chosen Option: **Option 2**.

We establish strict plane isolation by decoupling the **Journal Plane** from the **Events Plane**.

### 1. Canonical Endpoint Architecture Table

| Architectural Plane | Canonical Endpoint | HTTP Method | Data Source | Strict Scope & Boundary Guarantee | Former / Misnamed Route | Deprecated Legacy Alias |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Journal Plane** | `/api/v1/journal/latest` | `GET` | Active file tail | Returns **only** the single most recent line parsed from the active `Journal.*.log`. Zero DB queries. | Same | — |
| **Journal Plane** | `/api/v1/journal/events` | `GET` | SQLite DB (WAL) | **Strictly Frontier Journal Events.** Enforces `WHERE topic NOT LIKE 'telemetry.%'`. Guaranteed zero auxiliary/file-delta records. | `/api/v1/journal/query` | `/api/v1/events` (redirects to general events plane) |
| **Events Plane** | `/api/v1/events/query` *(alias `/api/v1/events`)* | `GET` | SQLite DB (WAL) | **Unified Event Store Query.** Unfiltered access to complete ingestion persistence store (`journal.*` + `telemetry.file_delta`). | Aliased to `/api/v1/journal/query` | `/api/v1/events` |
| **Events Plane** | `/api/v1/events/queue` | `GET` | In-memory ring buffer | Drains uncommitted batch events from the transmission ring buffer across all topics. | `/api/v1/journal/queue` | `/api/v1/events/buffer` |
| **Events Plane** | `/api/v1/events/stream` *(alias `/stream`)* | `GET` | SSE Transmitter | Unified real-time SSE stream dispatching both journal events (`journal.event`) and metadata deltas (`telemetry.file_delta`). | `/api/v1/journal/stream` | `/api/v1/stream` |
| **State Plane** | `/api/v1/state` | `GET` | In-memory cache | Consolidated ambient state: latest journal event + latest `Status.json` + all snapshot files. | Same | `/api/v1/telemetry/head` |
| **State Plane** | `/api/v1/state/heartbeat` | `GET` | Monotonic tracker | Sub-200 byte sequence and hash heartbeat. | Same | — |
| **Status Plane** | `/api/v1/status` | `GET` | In-memory cache | Cockpit flags and hardware status from `Status.json` only. | Same | `/api/v1/status/game` |
| **Snapshots Plane** | `/api/v1/snapshots` | `GET` | In-memory cache | Map of all 9 registered companion snapshot JSON files. | Same | — |
| **Snapshots Plane** | `/api/v1/snapshots/{name}` | `GET` | In-memory cache | Single snapshot JSON file payload (e.g. `Cargo.json`). | Same | — |
| **System Plane** | `/api/v1/system/watcher` | `GET` | Watcher reactor | Monitored directory path, poll interval, thread health. | Same | `/api/v1/status` (old semantics) |
| **System Plane** | `/api/v1/system/health` | `GET` | In-memory | Daemon liveness probe. | Same | `/api/v1/health` |
| **System Plane** | `/api/v1/system/logs` | `GET` | Logging buffer | Internal daemon operational diagnostic logs. | Same | `/api/v1/diagnostics/logs` |
| **System Plane** | `/api/v1/system/control` | `POST` | Reactor thread | Runtime directory re-binding and watcher thread control. | Same | `/api/v1/control/watch` |

---

### 2. Architectural Invariants

* **Invariant 1 (Journal Plane Isolation):** Any endpoint path prefixed with `/api/v1/journal/` interacts strictly and exclusively with Frontier Developments `Journal.*.log` artifacts. `/api/v1/journal/events` queries SQLite with mandatory filtering excluding non-journal topics (`topic NOT LIKE 'telemetry.%'`).
* **Invariant 2 (Events Plane Scope):** Any endpoint prefixed with `/api/v1/events/` provides cross-cutting access across the complete event store and transmitter pipeline. Responses from this plane declare `X-Telemetry-Plane: events`.
* **Invariant 3 (Backward Compatibility):**
  * `/api/v1/journal/query` is retained as a deprecated alias forwarding to `/api/v1/journal/events`.
  * `/api/v1/journal/queue` is retained as a deprecated alias forwarding to `/api/v1/events/queue`.
  * `/api/v1/journal/stream` is retained as a deprecated alias forwarding to `/api/v1/events/stream`.
  * `/api/v1/events` is retained as an alias for `/api/v1/events/query`.
  * `/api/v1/stream` is retained as an alias for `/api/v1/events/stream`.
