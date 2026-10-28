---
title: "ADR 0034: Configurable Database Retention and Maintenance"
status: "accepted"
date: "2026-10-28"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0020", "ADR 0022", "ADR 0025"]
informed: ["All Engineers"]
tags: ["adr", "storage", "sqlite", "retention", "maintenance", "cli"]
---

# ADR 0034: Configurable Database Retention and Maintenance

## Context and Problem Statement

[ADR 0022](0022_sqlite_persistence_event_querying_and_http_api_adapter.md) established SQLite in WAL mode as the persistent storage engine for historical telemetry events. The `telemetry_events` table is designed as an immutable append-only ledger.

Currently, events persist indefinitely. While typical Elite Dangerous telemetry produces modest volumes (10–40 MB over months of continuous play), retaining records ad infinitum without operator pruning controls or storage observability presents several challenges:
1. Long-running host test environments or headless servers accumulate stale telemetry without maintenance capabilities.
2. Developers require deep historical persistence across test iterations, whereas production or embedded users (e.g. Steam Deck) may prioritize bounded disk consumption.
3. Silent, automatic deletion of historical telemetry violates user trust (loss of historical flight or exploration logs), yet the complete absence of retention options is an anti-pattern.

How should `ed-telemetry` balance developer persistence requirements, long-term flight chronicle preservation, and operator maintenance controls?

## Decision Drivers

* **Default Indefinite Retention (Principle of Least Astonishment):** Telemetry represents irreversible game flight history. Never silently prune historical records unless explicitly configured by the operator.
* **Evolutionary Readiness for Full Release:** Acknowledge that while pre-1.0 development defaults to indefinite retention, full release (v1.0+) packaging may introduce sensible default retention thresholds (e.g. 90 or 180 days) based on telemetry usage statistics.
* **Deterministic Opt-In Retention Bounds:** Allow operators and automated services to specify age-based (`--retention-days`) and volume-based (`--retention-max-records`) pruning limits via CLI flags and environment variables.
* **Dedicated Administrative CLI Family (`db`):** Provide first-class operator tools (`status`, `prune`, `vacuum`) for inspectability and on-demand maintenance.
* **Hexagonal Boundary Purity:** Database maintenance operations must be formalized as domain use cases and boundary ports, keeping SQLite schema and SQL statements strictly isolated inside driven adapters (`adapters/driven/persistence`).

## Considered Options

* **Option 1: Hardcoded Rolling Window (e.g. 30 Days).** Automatically delete events older than 30 days on startup or ingestion. *(Rejected: Destructive to long-range exploration logs; violates developer requirements for deep datasets).*
* **Option 2: Status Quo (Uncapped Indefinite Retention without Pruning Tools).** Rely entirely on external SQLite CLI tools or file deletion. *(Rejected: Poor operator experience; fails to provide maintenance tools or bounded storage options).*
* **Option 3: Default Indefinite Retention with Opt-In Pruning and `db` CLI Family.** Maintain indefinite retention by default, provide optional daemon retention flags, and introduce an administrative `ed-telemetry db` command family.

## Decision Outcome

Chosen Option: **Option 3: Default Indefinite Retention with Opt-In Pruning and `db` CLI Family**.

### Architectural Invariants & Mechanics

* **Invariant 1 (Default Retention):** In the current lifecycle stage, `retention_days` and `retention_max_records` default to `None` (unlimited). Historical records persist indefinitely until explicitly pruned.
* **Invariant 2 (Full Release Review Gate):** Prior to v1.0 general availability, default retention behavior must be formally revisited to evaluate whether automated default aging (e.g., 180 days with archival prompting) is warranted for consumer releases.
* **Invariant 3 (Opt-In Daemon Pruning):** `ed-telemetry serve` accepts `--retention-days <N>` and `--retention-max-records <N>` (or `ED_DB_RETENTION_DAYS`, `ED_DB_MAX_RECORDS`). If configured, the daemon performs a non-blocking pruning pass at startup and upon graceful shutdown.
* **Invariant 4 (Administrative CLI Subcommands):** The CLI provides an `ed-telemetry db` subcommand family:
  * `ed-telemetry db status`: Displays database path, file size on disk, total event count, oldest event timestamp, and newest event timestamp (`--json` supported).
  * `ed-telemetry db prune`: Prunes records older than `--days <N>` and/or oldest records exceeding `--max-records <N>`, with optional `--vacuum` and confirmation gate (`--force` for automation).
  * `ed-telemetry db vacuum`: Executes SQLite `VACUUM` to defragment storage and return free pages to the host OS filesystem.
* **Invariant 5 (Atomic & Clean Cleanup):** Pruning uses index-backed SQL deletes (`DELETE FROM telemetry_events WHERE timestamp < ?` or subquery on row limits) executed within a single transaction.

## Positive Consequences

* Developers maintain full persistence without risk of arbitrary data expiration.
* Operators gain complete visibility into database storage size and event counts via `ed-telemetry db status`.
* Systems with constrained storage (Steam Deck, secondary laptops) can configure bounded retention seamlessly via flags or environment variables.
