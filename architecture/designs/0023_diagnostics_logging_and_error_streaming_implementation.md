---
title: "SDD-023: Diagnostics Logging, Error Bubbling, and API Transport Implementation"
tags: ["sdd", "logging", "diagnostics", "api", "streaming", "hexagonal"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-023: Diagnostics Logging, Error Bubbling, and API Transport Implementation

## 1. Executive Summary
This design document defines the structural interfaces, DTO definitions, error bubbling pipelines, and test specifications implementing ADR 0025.

## 2. Architecture & Event Flow

```
                      [ Python Logging ]             [ Watcher Audit Engine ]
                              │                                  │
                              ▼                                  ▼
                   ┌──────────────────────┐           ┌──────────────────────┐
                   │ DiagnosticLogBuffer  │           │   WatcherAuditEvent  │
                   │ (logging.Handler)    │           └──────────┬───────────┘
                   └──────────┬───────────┘                      │
                              │                                  ▼
                              │                    ┌───────────────────────────┐
                              │                    │ProcessTelemetryStreamUCase│
                              │                    └─────────────┬─────────────┘
                              │                                  │ TelemetryPayloadDTO
                              │                                  │ (topic: telemetry.audit)
                              │                                  ▼
                              │                    ┌───────────────────────────┐
                              │                    │  CompositeEgressAdapter   │
                              │                    └──────┬─────────────┬──────┘
                              │                           │             │
                              ▼                           ▼             ▼
                   ┌──────────────────────┐      ┌──────────────┐ ┌────────────┐
                   │GetDiagnosticLogsUCase│      │BufferedQueue │ │SqliteEgress│
                   └──────────┬───────────┘      └──────┬───────┘ └─────┬──────┘
                              │                         │               │
                              ▼                         ▼               ▼
                   ┌───────────────────────────────────────────────────────────┐
                   │                      HttpApiAdapter                       │
                   ├────────────────────────────┬──────────────────────────────┤
                   │ GET /api/v1/diagnostics/log│ GET /api/v1/stream (SSE)     │
                   │                            │ GET /api/v1/events?topic=... │
                   └────────────────────────────┴──────────────────────────────┘
```

## 3. Required Modifications & New Components

### 3.1 Domain Ports & DTOs
1. **`core/ports/dto/telemetry_dto.py`**:
   - `DiagnosticLogRecordDTO`:
     ```python
     @dataclass(frozen=True, slots=True)
     class DiagnosticLogRecordDTO(DataTransferObject):
         timestamp: datetime
         level: str
         logger_name: str
         message: str
     ```
   - `DiagnosticLogSnapshotDTO`:
     ```python
     @dataclass(frozen=True, slots=True)
     class DiagnosticLogSnapshotDTO(DataTransferObject):
         records: tuple[DiagnosticLogRecordDTO, ...]
         total_retained: int
     ```
2. **`core/ports/driven/telemetry_driven_port.py`**:
   - `DiagnosticLogPort`:
     ```python
     @runtime_checkable
     class DiagnosticLogPort(DrivenPort, Protocol):
         def get_recent_logs(self, min_level: str | None = None, limit: int = 100) -> DiagnosticLogSnapshotDTO: ...
     ```
3. **`core/ports/driving/telemetry_port.py`**:
   - `GetDiagnosticLogsPort`:
     ```python
     @runtime_checkable
     class GetDiagnosticLogsPort(DrivingPort, Protocol):
         def get_logs(self, min_level: str | None = None, limit: int = 100) -> DiagnosticLogSnapshotDTO: ...
     ```

### 3.2 Driven Adapter: In-Memory Diagnostic Log Buffer
- Create `src/ed_telemetry/adapters/driven/logging/buffer.py`:
  - `DiagnosticLogBuffer(logging.Handler, DiagnosticLogPort)`
  - Thread-safe ring buffer (using `collections.deque(maxlen=capacity)`).
  - Captures standard library `logging.LogRecord` instances and converts them to `DiagnosticLogRecordDTO`.

### 3.3 Core Use Case: `GetDiagnosticLogsUseCase`
- Create `src/ed_telemetry/core/use_cases/get_diagnostic_logs.py`:
  - Interactor satisfying `GetDiagnosticLogsPort` and delegating to `DiagnosticLogPort`.

### 3.4 Ingestion Stream Audit Forwarding (Option A)
- Update `ProcessTelemetryStreamUseCase`:
  - Register an audit callback:
    ```python
    self._watcher.register_audit_handler(self._handle_audit_event)
    ```
  - Forward audit events as JSON envelopes under topic `telemetry.audit`:
    ```python
    def _handle_audit_event(self, event: WatcherAuditEventDTO) -> None:
        payload_bytes = json.dumps(asdict(event)).encode("utf-8")
        payload = TelemetryPayloadDTO(
            topic="telemetry.audit",
            timestamp=event.timestamp,
            payload_bytes=payload_bytes,
            metadata=(("action", event.action),),
        )
        self._egress.send(payload)
    ```

### 3.5 Driving Adapter: API Route (Option B)
- Update `HttpApiAdapter`:
  - Add route `GET /api/v1/diagnostics/logs`.
  - Accepts query parameters `?min_level=INFO|WARNING|ERROR` and `?limit=50`.
  - Returns `DiagnosticLogSnapshotDTO` as JSON.

### 3.6 Driving Adapter: CLI Enhancements
Update `CliTelemetryAdapter` (`src/ed_telemetry/adapters/driving/cli/main.py`):
1. **Subcommand `logs`**:
   - Parses `--level {DEBUG,INFO,WARNING,ERROR}`, `--limit <int>`, and `--json`.
   - Invokes injected `GetDiagnosticLogsPort.get_logs()`.
   - Formats log entries with colored or tagged timestamp, level, and message.
2. **Subcommand `tail`**:
   - Parses `--topic <str>` (default: None for all, or `telemetry.audit` for control events) and `--json`.
   - Invokes injected `GetTelemetryStreamPort.stream_events()`.
   - Streams live output lines to stdout until interrupted (`Ctrl+C`).
3. **Subcommand `serve` options**:
   - Adds `--log-level` and `--log-file` configuring the root rotating file and console logger.

### 3.7 Cross-Platform Log Path Resolution & Rotation
Implement `resolve_default_log_path(platform: SupportedPlatform | None = None) -> Path`:
1. **Windows Path Strategy:**
   - Evaluates `%LOCALAPPDATA%\ed-telemetry\logs\ed-telemetry.log`.
   - Fallback: `%USERPROFILE%\.cache\ed-telemetry\logs\ed-telemetry.log`.
2. **Linux / SteamDeck Strategy:**
   - Evaluates `${XDG_STATE_HOME:-~/.local/state}/ed-telemetry/ed-telemetry.log`.
   - Fallback: `~/.cache/ed-telemetry/logs/ed-telemetry.log`.
3. **Rotating File Configuration:**
   - `RotatingFileHandler(log_path, maxBytes=5_242_880, backupCount=3, encoding='utf-8')`.
   - Ensured directory creation via `log_path.parent.mkdir(parents=True, exist_ok=True)`.
   - Deterministic file handler closure on shutdown to prevent Windows sharing locks.

## 4. Verification & Testing Strategy

1. **Unit Tests (`tests/unit/adapters/test_diagnostic_logging.py` & `test_cli_adapter.py`)**:
   - Test `DiagnosticLogBuffer` thread-safety, level filtering, and capacity bounds.
   - Test audit event bubbling from `ProcessTelemetryStreamUseCase` into `CompositeEgressAdapter`.
   - Test CLI `logs` and `tail` subcommands and argument validation.
   - Test `resolve_default_log_path` on Linux and mocked Windows environments.
2. **API Tests (`tests/unit/adapters/test_http_api.py`)**:
   - Test `GET /api/v1/diagnostics/logs` for 200 responses and level filtering.
   - Test `GET /api/v1/stream` receiving `telemetry.audit` events.
3. **Cross-Platform Wine Validation (`scripts/run_wine_tests.sh`)**:
   - Verify `resolve_default_log_path` resolves to Windows `%LOCALAPPDATA%` under Wine.
   - Verify `RotatingFileHandler` writes, rotates, and closes without `[WinError 32]` file sharing locks.
   - Verify CLI `logs` and `tail` subcommands under Windows NT simulant.
