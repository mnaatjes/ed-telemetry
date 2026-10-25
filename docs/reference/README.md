---
title: "Technical Reference"
tags: ["documentation", "reference", "api"]
created_at: "2026-10-06"
last_updated_at: "2026-10-25"
---

# Technical Reference

Information-oriented technical descriptions, interface contracts, and architectural rules.

---

## 1. Operating Interfaces & Telemetry Sinks

| Document | Topic | Target Audience |
| :--- | :--- | :--- |
| [CLI Command Reference](cli_interface.md) | `ed-telemetry` subcommands, parameters, and exit codes | Operators / Integrators |
| [HTTP REST & SSE API Reference](http_api_endpoints.md) | REST routes, SSE format, query parameters, RFC 7807 | Dashboard & App Developers |
| [Diagnostic Logging & Storage Reference](diagnostic_logging_and_storage.md) | Log file paths, rotation, ring buffer, SQLite WAL | Systems Engineers / Integrators |

---

## 2. Hexagonal Domain & Architecture Governance

| Document | Topic | Target Audience |
| :--- | :--- | :--- |
| [Hexagonal Architecture Invariant Rules](hexagonal_rules.md) | Governing architectural Truths (HEXA-TRUTH-01 to 05) | Core Contributors / Reviewers |
| [FileSystemWatcher Driving Adapter API](watcher_filesystem_adapter.md) | `FileSystemWatcher`, `WatcherPort`, threading lifecycle | Core Contributors |
| [OS Path Discovery API](watcher_path_discovery.md) | `PathDiscoverer`, platform strategies, models | Core Contributors |
| [Journal Candidate Selector API](watcher_journal_selector.md) | `JournalSelector`, `JournalCandidate`, sorting, succession | Core Contributors |
| [Status & Snapshot Identifier API](watcher_snapshot_identifier.md) | `SnapshotIdentifier`, `SnapshotRegistry`, case normalization | Core Contributors |
| [Ingestion Engine & Reactor API](watcher_engine.md) | `WatcherReactor`, `FileIngestionEvent`, `JournalTailer` | Core Contributors |
