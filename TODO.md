# Implementation TODO: ADR 0038 & SDD-033

- [x] **Step 1: Domain Models & DTO Enhancements**
  - [x] Add `state_sequence: int` to `TelemetryHeadDTO` in `src/ed_telemetry/core/ports/dto/telemetry_dto.py`
  - [x] Add `is_live_session: bool` to `GameStatusSnapshotDTO` and `AuxiliarySnapshotDTO` in `telemetry_dto.py`
  - [x] Add `TelemetryHeartbeatDTO` dataclass to `telemetry_dto.py`
  - [x] Export new DTOs in `__all__`

- [x] **Step 2: Driving Ports Definition**
  - [x] Add `GetTelemetryStatePort` and `GetStateHeartbeatPort` to `src/ed_telemetry/core/ports/driving/telemetry_port.py`
  - [x] Export new ports in `__all__`

- [x] **Step 3: State Sequence Counter & Storage Invariants**
  - [x] Implement atomic monotonic `StateSequenceTracker` (thread-safe counter incremented on journal lines and snapshot overwrites)
  - [x] Ingest snapshots on startup in `SnapshotReader` / `FileIngestionCoordinator` with `is_live_session=False` (Invariant 4)
  - [x] Mark `is_live_session=True` when reactor detects active file write

- [x] **Step 4: Core Use Cases Implementation**
  - [x] Implement `GetTelemetryStateUseCase` (realizing `GetTelemetryStatePort` and `GetTelemetryHeadPort` for backward compatibility)
  - [x] Enforce Invariant 1: 100% in-memory journal tail reader (`WatcherPort.read_active_journal_tail()`), zero SQLite repository calls
  - [x] Implement `GetStateHeartbeatUseCase` (realizing `GetStateHeartbeatPort`) returning `TelemetryHeartbeatDTO`

- [x] **Step 5: Driving HTTP Adapter Refactoring (`TelemetryHttpHandler`)**
  - [x] Implement Canonical Routes:
    - [x] `GET /api/v1/state`
    - [x] `GET /api/v1/state/heartbeat`
    - [x] `GET /api/v1/status`
    - [x] `GET /api/v1/snapshots` and `GET /api/v1/snapshots/{name}`
    - [x] `GET /api/v1/journal/latest`
    - [x] `GET /api/v1/journal/query`
    - [x] `GET /api/v1/journal/stream`
    - [x] `GET /api/v1/journal/queue`
    - [x] `GET /api/v1/system/health`
    - [x] `GET /api/v1/system/watcher`
    - [x] `GET /api/v1/system/logs`
    - [x] `POST /api/v1/system/control`
  - [x] Wire Legacy Route Aliases with exact parity:
    - [x] `/api/v1/telemetry/head` -> `/state`
    - [x] `/api/v1/status/game` -> `/status`
    - [x] `/api/v1/events` -> `/journal/query`
    - [x] `/api/v1/events/buffer` -> `/journal/queue`
    - [x] `/api/v1/stream` -> `/journal/stream`
    - [x] `/api/v1/health` -> `/system/health`
    - [x] `/api/v1/diagnostics/logs` -> `/system/logs`
    - [x] `/api/v1/control/watch` -> `/system/control`
  - [x] Implement Response Headers (`X-Telemetry-Source`, `X-Telemetry-Plane`, `ETag`) (Invariant 2)
  - [x] Implement HTTP 304 Not Modified caching on `/state` and `/state/heartbeat` via `If-None-Match`

- [x] **Step 6: Composition Root & Bootstrap Wiring**
  - [x] Update `src/ed_telemetry/bootstrap/container.py` and `build_container()` to wire new use cases and ports into `HttpApiAdapter`

- [x] **Step 7: OpenAPI Specification & Reference Docs Alignment**
  - [x] Update `architecture/api/openapi.yaml` with canonical paths, heartbeat, and response headers
  - [x] Update `docs/reference/http_api_endpoints.md` with canonical paths, deprecation notices, and header tables

- [x] **Step 8: Automated Quality Gates & Tests**
  - [x] Create `tests/architecture/test_api_standards.py` (Route regex conformance, OpenAPI synchrony, mandatory header verification)
  - [x] Update/expand `tests/unit/adapters/test_http_api.py` for all canonical endpoints, legacy aliases, 304 handling, Zero-DB isolation, and freshness flags
  - [x] Run `.venv/bin/python scripts/verify.py` to ensure pre-commit, import linter, mypy, and pytest all pass cleanly
