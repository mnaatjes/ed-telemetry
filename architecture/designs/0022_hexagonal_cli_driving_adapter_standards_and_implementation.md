---
title: "SDD-022: Hexagonal CLI Driving Adapter Standards and Implementation"
tags: ["sdd", "cli", "standards", "hexagonal", "implementation"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-022: Hexagonal CLI Driving Adapter Standards and Implementation

## 1. Executive Summary
This design document details the concrete implementation, subcommand structure, argument specifications, and test harnesses for the `CliTelemetryAdapter` driving adapter in accordance with ADR 0024.

## 2. Command Architecture & Subcommand Routing

```
                         ┌───────────────────────┐
                         │   ed-telemetry (CLI)  │
                         └───────────┬───────────┘
                                     │ argparse
            ┌────────────────┬───────┴────────┬───────────────┐
            ▼                ▼                ▼               ▼
      [ serve ]          [ status ]     [ status game ]   [ events ]
            │                │                │               │
            ▼                ▼                ▼               ▼
   ProcessTelemetryStream  GetWatcherStatus  GetGameStatus   FindTelemetryEvents
   & HttpApiAdapter.start()
```

### Subcommand Specifications

1. **`ed-telemetry serve`**
   - **Flags:**
     - `--host <str>` (default: `127.0.0.1`): HTTP API listening address.
     - `--port <int>` (default: `8080`): HTTP API listening port.
     - `--journal-dir <path>` (optional): Path to Elite Dangerous journal folder.
     - `--poll-interval <float>` (optional): Periodic poll interval in seconds.
   - **Behavior:**
     - Launches `process_telemetry_stream_use_case.start_streaming()`.
     - Starts `http_api_adapter.start()`.
     - Blocks gracefully until `SIGINT` (`Ctrl+C`) or `SIGTERM` is received.
     - Shuts down watcher and server deterministically.

2. **`ed-telemetry status`**
   - **Flags:**
     - `--json`: Format output as valid JSON.
   - **Behavior:**
     - Invokes `get_watcher_status_use_case.get_status()`.
     - Emits watcher active state, monitored directory, and active journal file.

3. **`ed-telemetry status game`**
   - **Flags:**
     - `--json`: Format output as valid JSON.
   - **Behavior:**
     - Invokes `get_latest_game_status_use_case.get_game_status()`.
     - Emits player cockpit status, coordinates, and timestamp.

4. **`ed-telemetry events`**
   - **Flags:**
     - `--topic <str>`: Filter by event topic (e.g. `telemetry.journal`).
     - `--since-id <int>`: Filter records newer than primary key ID.
     - `--limit <int>` (default: `20`): Maximum records to retrieve.
     - `--json`: Format output as valid JSON array.
   - **Behavior:**
     - Invokes `find_telemetry_events_use_case.find_events()`.
     - Displays formatted event tabular/list output.

## 3. Structural Adapter Refactoring

### Adapter Class: `src/ed_telemetry/adapters/driving/cli/main.py`
The refactored `CliTelemetryAdapter` accepts injected driving use cases:
```python
class CliTelemetryAdapter:
    def __init__(
        self,
        watcher_status_port: GetWatcherStatusPort,
        game_status_port: GetLatestGameStatusPort,
        find_events_port: FindTelemetryEventsPort,
        process_stream_port: ProcessTelemetryStreamPort,
        http_api_adapter: HttpApiAdapter,
    ) -> None: ...

    def run(self, argv: list[str] | None = None) -> int: ...
```

## 4. Architectural Boundaries & Quality Verification

1. **AST Linter Rule (`tests/architecture/test_boundaries.py`):**
   - Add test `test_no_third_party_cli_framework_imports` ensuring neither `click`, `typer`, `rich`, nor `docopt` are imported across the codebase.
2. **Unit Tests (`tests/unit/adapters/test_cli_adapter.py`):**
   - Verify argument parsing, `--json` serialization, error reporting, and clean exit codes across all subcommands.
3. **Cross-Platform Wine Validation (`scripts/run_wine_tests.sh`):**
   - Execute CLI subcommands under Windows NT / Wine simulant to verify console I/O and process lifecycle.
