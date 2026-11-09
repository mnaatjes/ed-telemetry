---
title: "ADR 0039: Server-Sent Events (SSE) File Delta Push Notifications"
status: "proposed"
date: "2026-11-09"
deciders: ["Core Architecture Team"]
consults: ["ADR 0023", "ADR 0038"]
informs: ["All Engineers"]
tags: ["adr", "api", "telemetry", "sse", "stream", "file-delta", "claim-check"]
---

# ADR 0039: Server-Sent Events (SSE) File Delta Push Notifications

## Context and Problem Statement

Downstream client applications (e.g. `ed-cli-core`, `tail_endpoint.py`, cockpit annunciator displays, copilot overlays) currently rely on periodic HTTP polling (`GET /api/v1/snapshots/*` and `GET /api/v1/status`) to detect when Frontier Developments writes updates to companion files on the filesystem (`Status.json`, `ModulesInfo.json`, `Cargo.json`, `ShipLocker.json`, `Market.json`, `Shipyard.json`, `Outfitting.json`, `NavRoute.json`, `Backpack.json`).

Periodic polling introduces notable architectural drawbacks:
1. **Unnecessary Network and CPU Overhead:** Polling loops generate repetitive HTTP handshakes, header processing, and JSON deserialization overhead even when files remain untouched for hours.
2. **Detection Latency vs. Resource Contention:** Short poll intervals (e.g. 250ms) consume CPU and bandwidth, while longer poll intervals (e.g. 2000ms) introduce perceptible lag into flight instruments.
3. **Stream Underutilization:** The existing SSE streaming endpoint (`/api/v1/stream` / `/api/v1/journal/stream`) emits an initial handshake (`{"event":"connected"}`) and tails active journal lines (`telemetry.journal`), but remains silent during non-journal file write events.

If `ed-telemetry` emits snapshot and status write events across the stream, should it push full hydrated JSON payloads into the SSE stream, or adopt a lightweight file-delta notification (claim-check) pattern?

---

## Decision Drivers

* **Claim-Check Simplicity:** The SSE stream must remain lightweight and responsive without being saturated by large payloads (e.g. 100+ KB commodity lists in `Market.json`).
* **Enforced Single Source of Truth:** Authoritative deserialization and schema hydration must remain anchored in dedicated REST endpoints (`/api/v1/snapshots/{name}`, `/api/v1/status`) to prevent duplicating business logic and hydration schemas inside stream serializers.
* **Low Server Overhead:** Ingestion worker threads must not parse or transform raw file data on disk solely to emit an SSE event.
* **Backward Compatibility:** Existing journal streaming consumers expecting `{"topic": "telemetry.journal", ...}` must not experience breaking changes.

---

## Decision Outcome

Chosen Option: **Adopt a Lightweight File-Delta Notification Stream Pattern (`telemetry.file_delta`) on `/api/v1/stream`**.

### 1. File Delta Message Specification

Whenever the filesystem watcher detects a modification or write event on any monitored companion file or active journal, it emits a lightweight delta notification JSON object over `/api/v1/stream` with the topic `telemetry.file_delta`:

```json
{
  "topic": "telemetry.file_delta",
  "target": "ModulesInfo.json",
  "action": "modified",
  "raw_hash": "43ef64b8e02f00b2",
  "timestamp": "2026-11-09T00:20:00.123456+00:00"
}
```

* **`topic`:** Fixed topic identifier `telemetry.file_delta`.
* **`target`:** Canonical filename that triggered the event (e.g., `ModulesInfo.json`, `Status.json`, `Cargo.json`, `ShipLocker.json`).
* **`action`:** File lifecycle action (`modified`, `created`).
* **`raw_hash`:** The 64-bit content hash (matching the HTTP `ETag` on the corresponding REST endpoint).
* **`timestamp`:** ISO-8601 UTC timestamp of event detection.

### 2. Client Consumption Workflow (Claim-Check)

1. **Initial Baseline:** The client queries `GET /api/v1/state` upon boot to hydrate baseline model state.
2. **Listen:** The client connects to `GET /api/v1/stream` (SSE).
3. **Filter & Fetch:** When receiving a `telemetry.file_delta` notification:
   * If the client is not tracking `target`, the event is dropped with $O(1)$ overhead.
   * If the client is actively tracking `target`, it performs a conditional REST fetch (`GET /api/v1/snapshots/{name}`) supplying `If-None-Match: <raw_hash>`.

---

## Pros and Cons

* **Good:** Minimal network bandwidth; SSE frames remain under 200 bytes.
* **Good:** Eliminates payload duplication across streaming and REST serialization layers.
* **Good:** Zero client-side polling loops required to detect file modifications.
* **Bad:** Requires a follow-up HTTP request if the client requires the full hydrated data payload.
