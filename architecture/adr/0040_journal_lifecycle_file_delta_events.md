---
title: "ADR 0040: Journal Lifecycle and Part Rollover File Delta Stream Events"
status: "proposed"
date: "2026-11-09"
deciders: ["Core Architecture Team"]
consults: ["ADR 0039", "ADR 0006", "ADR 0009"]
informs: ["All Engineers"]
tags: ["adr", "api", "telemetry", "sse", "stream", "journal", "rollover", "file-delta"]
---

# ADR 0040: Journal Lifecycle and Part Rollover File Delta Stream Events

## Context and Problem Statement

ADR 0039 introduced lightweight Server-Sent Events (SSE) push notifications (`telemetry.file_delta`) on `/api/v1/stream` for companion snapshot and status files (`Status.json`, `ModulesInfo.json`, etc.) whenever filesystem writes occur.

However, journal log files (`Journal.<timestamp>.<part>.log`) currently only emit discrete log lines (`telemetry.journal`). When a new journal session begins or when the game client rotates the active log to a successor part (`PART_ROLLOVER`), the filesystem lifecycle transition itself is logged to control-plane audit buffers (`telemetry.audit`), but no file-delta notification is emitted on the stream.

Downstream clients adhering strictly to the Single Responsibility Principle (SRP) for filesystem monitoring need to know when physical journal files are created or rotated on disk without having to consume, parse, or understand in-game JSONL payloads.

---

## Decision Drivers

* **Single Responsibility Principle (SRP):** Filesystem observers must be able to track physical journal creation and rotation without coupling to gameplay event schemas.
* **Stream Uniformity:** File-delta stream events (`telemetry.file_delta`) must represent all physical telemetry files monitored on disk, including journals.
* **Zero Payload Overhead:** Retain the claim-check notification pattern: emit strictly metadata (`target`, `action`, `raw_hash`, `timestamp`) without journal contents.
* **Lifecycle State Clarity:** Distinguish between initial file binding (`action: "created"` or `"bound"`) and part rotation transitions (`action: "rollover"`).

---

## Decision Outcome

Chosen Option: **Emit `telemetry.file_delta` Events for Journal Creation and Part Rollovers**.

### 1. Specification

When `WatcherReactor` transitions journal states:
1. **Journal Creation / Initial Selection:**
   When the watcher binds a newly spawned journal file:
   ```json
   {
     "topic": "telemetry.file_delta",
     "target": "Journal.2026-11-09T011500.01.log",
     "action": "created",
     "raw_hash": "e3b0c44298fc1c14",
     "timestamp": "2026-11-09T01:15:00.000000+00:00"
   }
   ```

2. **Part Rollover Transition:**
   When the active journal reaches size limits and rotates to a successor part (e.g. part 1 to part 2):
   ```json
   {
     "topic": "telemetry.file_delta",
     "target": "Journal.2026-11-09T011500.02.log",
     "action": "rollover",
     "raw_hash": "e3b0c44298fc1c14",
     "timestamp": "2026-11-09T03:45:12.000000+00:00"
   }
   ```

### 2. Hexagonal Implementation Flow

In `ProcessTelemetryStreamUseCase._handle_audit_event`:
* Intercept `WatcherAuditEventDTO` with action `WatcherAuditAction.SELECTED` or `WatcherAuditAction.PART_ROLLOVER`.
* Translate the audit event into a standardized `TelemetryPayloadDTO` with topic `telemetry.file_delta`.
* Push the payload to `egress` for immediate streaming to connected SSE clients.

---

## Pros and Cons

* **Good:** Client file observers can monitor all filesystem changes uniformly without inspecting journal line content.
* **Good:** Maintains strict SRP boundary between file lifecycle tracking and game event deserialization.
* **Good:** Fully backward-compatible with existing consumers of `telemetry.journal` and `telemetry.snapshot`.
