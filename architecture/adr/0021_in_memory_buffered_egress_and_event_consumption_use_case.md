---
title: "ADR 0021: In-Memory Buffered Egress Adapter and Telemetry Event Consumption Use Case"
tags: ["adr", "egress", "buffered_queue", "use_cases", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# ADR 0021: In-Memory Buffered Egress Adapter and Telemetry Event Consumption Use Case

## Status
Accepted

## Context
In ADR 0020, `ed-telemetry` established a strict ingestion boundary: reading files, extracting raw bytes, and transmitting event payloads to outbound sinks.

`ProcessTelemetryStreamUseCase` ingests file events from `WatcherPort` and pushes `TelemetryPayloadDTO` out to `EgressPort`. However, driving adapters (like an API server, WebSocket bridge, or CLI consumer) require a mechanism to receive these events without violating the cardinal rule of Hexagonal Architecture: **Driving Adapters must only communicate with Use Cases, never directly with Driven Adapters.**

Furthermore, because file watching and operating system file flushes occur in bursts (e.g. dozens of lines written during a star system jump or station docking), a thread-safe in-memory shock absorber is required to decouple fast disk readers from downstream consumers.

## Decision

1. **Driven Read Port (`EventQueuePort`):**
   - Declare an abstract driven port `EventQueuePort` in `core/ports/driven/telemetry_driven_port.py`.
   - Defines read operations: `.poll(timeout)`, `.get_batch(limit, timeout)`, and `.queue_size()`.

2. **Dual-Port Driven Adapter (`BufferedQueueAdapter`):**
   - Implement `BufferedQueueAdapter` in `adapters/driven/egress/buffered_queue.py`.
   - Implements `EgressPort` (write side: `send(payload)`) and `EventQueuePort` (read side: `poll`, `get_batch`).
   - Uses standard library `queue.Queue` with configurable capacity and drop policies.

3. **Driving Consumption Port & Use Case (`GetTelemetryEventsUseCase`):**
   - Declare `GetTelemetryEventsPort` in `core/ports/driving/telemetry_port.py`.
   - Implement `GetTelemetryEventsUseCase` in `core/use_cases/get_telemetry_events.py` satisfying `GetTelemetryEventsPort`.
   - Coordinates with `EventQueuePort` to poll or batch-read `TelemetryBatchDTO` envelopes for driving adapters.

4. **Composition Root Wiring:**
   - Update `build_container()` to wire `BufferedQueueAdapter` by default, connecting `ProcessTelemetryStreamUseCase` (writer) and `GetTelemetryEventsUseCase` (reader).

## Consequences
- The cardinal hexagonal rule is strictly preserved: Driving Adapters (API/CLI) interact strictly through `GetTelemetryEventsUseCase`.
- Ingestion burst protection is achieved without external dependencies.
- Unit testing can mock either the read or write side of the buffer using fake doubles.
