---
title: "SDD-019: In-Memory Buffered Egress Adapter and Telemetry Event Consumption Use Case"
tags: ["sdd", "egress", "buffered_queue", "use_cases", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-019: In-Memory Buffered Egress Adapter and Telemetry Event Consumption Use Case

## 1. Executive Summary
This design document details the structural design, interfaces, and mechanics of the in-memory buffered egress architecture formalizing ADR 0021. It introduces `EventQueuePort`, `BufferedQueueAdapter`, and `GetTelemetryEventsUseCase` to bridge telemetry ingestion to driving consumer adapters without architectural boundary violations.

## 2. Structural Topology & Sequence

```
[Inbound Driven: FileSystemWatcher]
        │
        │ FileIngestionEventDTO
        ▼
[ProcessTelemetryStreamUseCase]
        │
        │ TelemetryPayloadDTO (via EgressPort.send)
        ▼
┌────────────────────────────────────────────────────────┐
│            BufferedQueueAdapter                        │
│   (Implements EgressPort AND EventQueuePort)           │
│   - queue.Queue[TelemetryPayloadDTO]                   │
└────────────────────────────────────────────────────────┘
        ▲
        │ TelemetryBatchDTO (via EventQueuePort.get_batch)
        │
[GetTelemetryEventsUseCase]
        ▲
        │ get_events(limit, timeout)
        │
[Driving Adapter: API Server / CLI]
```

## 3. Boundary Contracts & Specifications

### 3.1 DTOs (`core/ports/dto/telemetry_dto.py`)
```python
@dataclass(frozen=True, slots=True)
class TelemetryBatchDTO(DataTransferObject):
    events: tuple[TelemetryPayloadDTO, ...]
    remaining_count: int
    dropped_count: int
```

### 3.2 Driven Port (`core/ports/driven/telemetry_driven_port.py`)
```python
@runtime_checkable
class EventQueuePort(DrivenPort, Protocol):
    def poll(self, timeout: float | None = None) -> TelemetryPayloadDTO | None: ...
    def get_batch(self, limit: int = 100, timeout: float | None = None) -> TelemetryBatchDTO: ...
    def queue_size(self) -> int: ...
```

### 3.3 Driving Port (`core/ports/driving/telemetry_port.py`)
```python
@runtime_checkable
class GetTelemetryEventsPort(DrivingPort, Protocol):
    def get_events(self, limit: int = 100, timeout: float | None = None) -> TelemetryBatchDTO: ...
```

### 3.4 Driven Adapter (`adapters/driven/egress/buffered_queue.py`)
`BufferedQueueAdapter(EgressPort, EventQueuePort)`:
- Backed by `queue.Queue[TelemetryPayloadDTO](maxsize=maxsize)`.
- If `maxsize > 0` and the queue is full, drops the oldest or newest event according to policy and increments `dropped_count`.
- Thread-safe across watcher producer thread and consumer threads.

### 3.5 Use Case (`core/use_cases/get_telemetry_events.py`)
`GetTelemetryEventsUseCase(GetTelemetryEventsPort)`:
- Injected with `queue: EventQueuePort`.
- Invokes `queue.get_batch(limit=limit, timeout=timeout)` and returns `TelemetryBatchDTO`.

## 4. Verification Plan
- Unit tests for `BufferedQueueAdapter` under concurrency.
- Unit tests for `GetTelemetryEventsUseCase` using fake double.
- End-to-end integration test verifying ingestion to queue and consumption by use case.
- Wine simulation verification in `scripts/run_wine_tests.sh`.
