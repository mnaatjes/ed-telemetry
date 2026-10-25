---
title: "SDD-024: Documentation Realignment with Diataxis Framework and SDK Retirement"
tags: ["sdd", "documentation", "diataxis", "cli", "logging", "api"]
created_at: "2026-10-25"
last_updated_at: "2026-10-25"
---

# SDD-024: Documentation Realignment with Diataxis Framework and SDK Retirement

## 1. System Overview

This Software Design Document specifies the concrete files, modifications, and schema alignments required to bring the documentation plane (`docs/`) and project overview (`README.md`) into total parity with package version `v0.4.0` under the Diátaxis framework.

## 2. Diátaxis Plane Architecture

```text
docs/
├── how-to/                                  # Task-focused operational guides
│   ├── README.md                            # Quadrant index
│   ├── run_cli_daemon.md                    # Running daemon, CLI commands, flags
│   ├── inspect_logs_and_diagnostics.md      # Local files, ring buffer, tailing
│   ├── consume_telemetry_http_api.md        # REST queries, SSE, RFC 7807 handling
│   ├── verify_architecture_and_test_locally.md
│   └── test_cross_platform_locally.md
│
├── reference/                               # Information-oriented technical descriptions
│   ├── README.md                            # Quadrant index
│   ├── cli_interface.md                     # CLI subcommands, arguments, exit codes
│   ├── http_api_endpoints.md                # REST/SSE routes, params, payloads
│   ├── diagnostic_logging_and_storage.md    # Log paths, ring buffer, audit envelopes
│   ├── hexagonal_rules.md                   # Governing architectural Truths
│   ├── watcher_filesystem_adapter.md        # FileSystemWatcher driver API
│   ├── watcher_path_discovery.md            # Path discovery strategies
│   ├── watcher_journal_selector.md          # Candidate sorting & succession
│   ├── watcher_snapshot_identifier.md       # Status & snapshot identification
│   └── watcher_engine.md                    # Ingestion reactor loop
│
├── explanation/
│   └── README.md
│
└── tutorials/
    └── README.md
```

## 3. Implementation Specifications

### 3.1 Pruning & Migration
1. **Purge Defunct Guides:**
   - Delete `docs/how-to/add_application_service.md`
   - Delete `docs/how-to/register_driven_adapter.md`
   - Delete `docs/how-to/create_driven_adapter_registry.md`
   - Delete `docs/how-to/classify_driven_adapter_interaction_path.md`
   - Delete `docs/how-to/determine_use_case_facades.md`
   - Delete `docs/reference/application_scaffolding.md`
2. **Purge Defunct SDK:**
   - Remove `sdk/` directory.

### 3.2 Main `README.md`
- Replace topology tree with pure hexagonal structure: `src/ed_telemetry/{core,adapters,bootstrap}`.
- Provide quick-start installation (`pip install -e .`), execution examples (`ed-telemetry serve`), API endpoints overview, and testing instructions.

### 3.3 New and Updated How-To Guides
1. **`docs/how-to/run_cli_daemon.md`**:
   - Update commands: `ed-telemetry serve`, `status`, `events`, `logs`, `tail`.
   - Explain daemon options (`--host`, `--port`, `--log-level`, `--log-file`).
2. **`docs/how-to/inspect_logs_and_diagnostics.md`**:
   - Location of rotating logs: `%LOCALAPPDATA%\ed-telemetry\logs\ed-telemetry.log` (Windows) and `~/.local/state/ed-telemetry/ed-telemetry.log` (Linux).
   - How to query in-memory diagnostic buffer via `ed-telemetry logs` and `GET /api/v1/diagnostics/logs`.
   - How to follow live telemetry and error/audit streams using `ed-telemetry tail --topic telemetry.audit`.
3. **`docs/how-to/consume_telemetry_http_api.md`**:
   - Connecting to `http://127.0.0.1:8080/api/v1`.
   - Polling endpoints (`/api/v1/status`, `/api/v1/status/game`, `/api/v1/snapshots/{name}`).
   - Subscribing to Server-Sent Events (`/api/v1/stream`).
   - Querying historical SQLite events (`/api/v1/events?topic=...&since_id=...`).
   - Parsing RFC 7807 Problem Details on HTTP 4xx/5xx errors.

### 3.4 Technical References
1. **`docs/reference/cli_interface.md`**: Comprehensive specification of all subcommands, arguments, output formats, and exit codes.
2. **`docs/reference/http_api_endpoints.md`**: Complete REST & SSE API specification with HTTP methods, query parameters, status codes, and JSON response envelopes.
3. **`docs/reference/diagnostic_logging_and_storage.md`**: Authoritative specification of logging paths, rotation policy (5 MB $\times$ 3), ring buffer configuration, and `WatcherAuditEventDTO` schema.
