---
title: "ADR 0036: Non-Destructive Telemetry Head State Endpoint and Reverse Index Queries"
status: "accepted"
date: "2026-11-04"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0021", "ADR 0022", "ADR 0023", "ADR 0035"]
informed: ["All Engineers"]
tags: ["adr", "api", "telemetry", "streaming", "head-state", "facade"]
---

# ADR 0036: Non-Destructive Telemetry Head State Endpoint and Reverse Index Queries

## Context and Problem Statement

Downstream fleet tools (such as `ed-integration-smoke`'s Ambient Telemetry Facade, copilot CLIs, and real-time dashboard annunciators) need instantaneous, non-destructive access to the current state of active gameplay:
1. *Where is the commander right now?* (Latest system, body, coordinates from `Location` / `FSDJump`).
2. *What is the ship doing right now?* (Latest `Status.json` cockpit bitfields and pips).
3. *What are the current flight plans or local station data?* (Latest `NavRoute.json`, `Market.json`, `Cargo.json`).

Historically, `ed-telemetry` provided two access patterns for event retrieval:
* **The In-Memory Ring Buffer (`/api/v1/events/buffer`):** An in-memory FIFO queue designed for streaming consumption. Calling this endpoint **destructively pops** events from oldest to newest. If a client connects after hours of gameplay, it is forced to paginate through and drain thousands of stale records before reaching current events. Furthermore, if multiple clients query this endpoint, they steal events from each other.
* **The Persistent Database Query (`/api/v1/events`):** Queries SQLite using `ORDER BY id ASC LIMIT ?`. While non-destructive, it only allows forward replay from `id=1` or `since_id`. A client seeking the *latest* state cannot query backwards without knowing the highest database ID in advance.

This architectural gap forces downstream clients to either drain thousands of unneeded historical buffer items (generating excessive network traffic and starvation) or execute multiple round-trips to probe the database boundary.

How should `ed-telemetry` provide an immediate, non-destructive, single-round-trip snapshot of the active game head state?

## Decision Drivers

* **Single HTTP Round-Trip:** Downstream copilots and facades must be able to resolve complete ambient context (latest journal event, latest cockpit status, and active out-of-band snapshots) in a single request.
* **Non-Destructive State Access:** Reading current state must never mutate or dequeue items from the in-memory streaming ring buffer or affect other concurrent readers.
* **Multi-Reader Concurrency:** Multiple autonomous processes (dashboards, audit trackers, copilots) must observe current game telemetry simultaneously without race conditions or event loss.
* **Zero Cold-Start Lag:** Cold clients starting mid-session must obtain instantaneous current telemetry without draining historical backpressure.
* **Hexagonal Architectural Purity:** The solution must cleanly traverse driving HTTP adapters, domain use cases, and driven persistence/snapshot ports without leaky abstractions.

## Considered Options

* **Option 1: Aggressive Buffer Draining by Clients.** Require clients to repeatedly poll `/api/v1/events/buffer` until `remaining_count == 0`. *(Rejected: Severe architectural antipattern; starves other readers, wastes bandwidth, and creates cold-start delays).*
* **Option 2: Add Reverse Ordering (`order=desc`) to `/api/v1/events`.** Allow sorting by `id DESC`. *(Partially accepted, but insufficient on its own: Returns the latest journal event, but still requires separate HTTP requests for `Status.json`, `NavRoute.json`, and `Market.json`).*
* **Option 3: Dedicated Consolidated Head Endpoint (`/api/v1/telemetry/head`) + Reverse Query Support (Selected).** Introduce a composite endpoint delivering the latest journal event, active cockpit status, and registered snapshot payloads in a single response, accompanied by `order=desc` support on `/api/v1/events`.

## Decision Outcome

Chosen Option: **Option 3: Dedicated Consolidated Head Endpoint (`/api/v1/telemetry/head`) + Reverse Query Support**.

### Architectural Invariants & Mechanics

* **Invariant 1 (Consolidated Head Resource):** `GET /api/v1/telemetry/head` is established as the canonical, non-destructive state inspection endpoint:
  ```json
  {
    "timestamp": "2026-11-04T01:35:44Z",
    "active_journal": "Journal.2026-11-03T201036.01.log",
    "latest_journal_event": {
      "id": 12845,
      "event_id": "telemetry.journal_1793746544.123456",
      "topic": "telemetry.journal",
      "timestamp": "2026-11-04T01:35:18Z",
      "payload": { ... }
    },
    "game_status": {
      "timestamp": "2026-11-04T01:35:44Z",
      "raw_payload": { ... }
    },
    "snapshots": {
      "NavRoute": { ... },
      "Market": { ... },
      "Cargo": { ... }
    }
  }
  ```
* **Invariant 2 (Non-Destructive In-Memory Access):** The head endpoint reads directly from in-memory cached references maintained by the file watcher and snapshot ports, falling back to non-popping database reads. It does not touch the ring buffer queue.
* **Invariant 3 (Bidirectional Database Pagination):** `/api/v1/events` is expanded to accept `order=asc|desc` (defaulting to `asc` for backward compatibility). When `order=desc`, the repository executes `SELECT ... ORDER BY id DESC LIMIT ?`.
* **Invariant 4 (Domain Boundary Decoupling):** A new domain use case `GetTelemetryHeadUseCase` orchestrates data from `FindEventsPort`, `GameStatusPort`, and `AuxSnapshotPort`.

## Positive Consequences

* Solves the Ambient Telemetry Facade requirements in `ed-integration-smoke` with a single HTTP round-trip.
* Eliminates the ring buffer draining antipattern and prevents multi-reader event starvation.
* Provides $O(1)$ reverse queries for recent telemetry events via `/api/v1/events?order=desc&limit=N`.
* Preserves complete backward compatibility for existing SSE streaming and sequential replay consumers.
