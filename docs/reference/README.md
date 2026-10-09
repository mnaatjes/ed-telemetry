---
title: "Technical Reference"
tags: ["documentation", "reference", "api"]
created_at: "2026-10-06"
last_updated_at: "2026-10-09"
---

# Reference

Information-oriented technical descriptions, configuration specifications, and telemetry catalogs.

---

## Technical Specifications & API Catalogs

| Document | Topic | Target Audience |
| :--- | :--- | :--- |
| [OS Path Discovery API](watcher_path_discovery.md) | `PathDiscoverer`, platform strategies, models, and exceptions | Developers / SDK integrators |
| [Journal Candidate Selector API](watcher_journal_selector.md) | `JournalSelector`, `JournalCandidate`, sorting, and succession | Developers / SDK integrators |
| [Status & Snapshot Identifier API](watcher_snapshot_identifier.md) | `SnapshotIdentifier`, `SnapshotRegistry`, casing normalization | Developers / SDK integrators |
| [Ingestion Engine & Reactor API](watcher_engine.md) | `WatcherReactor`, `FileIngestionEvent`, `JournalTailer`, `SnapshotReader` | Developers / SDK integrators |
| [FileSystemWatcher Driving Adapter API](watcher_filesystem_adapter.md) | `FileSystemWatcher`, `WatcherPort`, threading lifecycle, callbacks | Developers / SDK integrators |
| [Application Scaffolding API](application_scaffolding.md) | `ApplicationContext`, `DataTransferObject`, `BaseApplicationService`, base exceptions | Developers / SDK integrators |
