---
title: "SDD-026: Canonical CLI Streaming and Logging Alignment"
status: "approved"
date: "2026-10-26"
author: "Core Architecture Team"
governing_adr: "architecture/adr/0028_canonical_cli_streaming_and_logging_alignment.md"
tags: ["sdd", "cli", "streaming", "logging", "design"]
---

# SDD-026: Canonical CLI Streaming and Logging Alignment

## 1. Executive Summary

This Software Design Document specifies the technical modifications to `CliTelemetryAdapter` (`src/ed_telemetry/adapters/driving/cli/main.py`) to align subcommands and streaming options with standard UNIX and cloud-native conventions:
1. Promote `stream` as the primary subcommand for real-time domain event streaming, keeping `tail` as an identical alias.
2. Add `-f` / `--follow` support to `logs` to follow the on-disk rotating application log file (`tail -f` behavior).
3. Add `-f` / `--follow` support to `events` to follow the live event feed directly after inspection.
4. Update Diátaxis operator manuals post-implementation.

---

## 2. CLI Grammar & Command Specification

### 2.1 Subcommand: `stream` (and alias `tail`)
Follows live domain event feeds (`telemetry.journal`, `telemetry.status`, `telemetry.snapshot`, `telemetry.audit`):
```bash
ed-telemetry stream [--topic TOPIC] [--json]
ed-telemetry tail [--topic TOPIC] [--json]
```

### 2.2 Subcommand: `logs`
Inspects point-in-time diagnostic logs or continuously follows new log output:
```bash
ed-telemetry logs [--level LEVEL] [--limit N] [--follow | -f] [--json]
```
* **Default Mode (Point-in-Time):** Queries the daemon's in-memory ring buffer via `GET /api/v1/diagnostics/logs` or parses the recent `limit` entries from disk.
* **Follow Mode (`-f` / `--follow`):** Opens `resolve_default_log_path()`, seeks to the end (or outputs initial recent lines), and continuously tails new lines with zero-dependency polling.

### 2.3 Subcommand: `events`
Queries historical events from SQLite or follows the live stream:
```bash
ed-telemetry events [--topic TOPIC] [--since-id ID] [--limit N] [--follow | -f] [--json]
```
* If `--follow` / `-f` is set, dispatches directly into `_handle_stream(args)`.

---

## 3. Implementation Details

### 3.1 Parser Updates (`_build_parser`)
1. Create `stream_parser` with `--topic` and `--json`.
2. Add `tail_parser` with identical arguments mapped to `_handle_stream`.
3. Add `-f`, `--follow` (action="store_true") to `logs_parser`.
4. Add `-f`, `--follow` (action="store_true") to `events_parser`.

### 3.2 Continuous Disk Log Tailer (`_tail_disk_logs`)
Implement pure Python log file follower:
```python
def _tail_disk_logs(self, log_path: Path, min_level: str | None, as_json: bool) -> None:
    # Ensure log file exists or wait for creation
    # Seek to end minus initial context
    # Loop while sleep(0.2) reading readline()
    # Apply regex filter and print matches
```

---

## 4. Verification Plan

1. **Unit Tests (`tests/unit/adapters/test_cli_adapter.py`):**
   * Test `stream` subcommand executes identically to `tail`.
   * Test `events --follow` dispatches to stream handler.
   * Test `logs --follow` invokes log tailing logic.
2. **Post-Implementation Documentation:**
   * Update `docs/how-to/run_cli_daemon.md` and `docs/reference/cli_interface.md`.
3. **Quality Gates:**
   * Run `scripts/verify.py` and `scripts/run_wine_tests.sh`.
