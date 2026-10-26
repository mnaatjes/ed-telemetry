---
title: "ADR 0028: Canonical CLI Streaming and Logging Alignment"
status: "accepted"
date: "2026-10-26"
decision_makers: ["Core Architecture Team"]
consulted: ["Operator Feedback", "POSIX / Cloud Native CLI Conventions"]
informed: ["All Contributors"]
tags: ["adr", "cli", "streaming", "logging", "standards"]
---

# ADR 0028: Canonical CLI Streaming and Logging Alignment

## Context and Problem Statement

The `ed-telemetry` CLI currently exposes five subcommands: `serve`, `status`, `events`, `logs`, and `tail`.

During operational review, operator ambiguity arose regarding the semantic distinction between `tail` and `logs`:
1. In UNIX and cloud infrastructure conventions (e.g., POSIX `tail -f`, Docker `docker logs -f`, Kubernetes `kubectl logs -f`), the term **`tail`** universally denotes continuously following **unstructured process logs, diagnostics, and stack traces**.
2. In `ed-telemetry`, the subcommand `tail` actually streams structured, multiplexed **domain and audit event feeds** (`telemetry.journal`, `telemetry.status`, `telemetry.audit`) produced by the reactive watcher engine over Server-Sent Events (SSE).
3. Meanwhile, `ed-telemetry logs` only supports point-in-time snapshot inspection and lacks a continuous streaming mode (`--follow` / `-f`).

How should the CLI subcommands and options be structured to align with industry CLI conventions while preserving backwards compatibility?

## Decision Drivers

* **Cognitive Alignment:** Commands must conform to standard industry semantics (Docker, Kubernetes, Kafka, UNIX).
* **Strict Semantic Segregation:** Structured business telemetry event streaming (`/stream`) must be clearly distinguished from unstructured daemon process logs (`ed-telemetry.log`).
* **Zero Breaking Changes:** Existing operators and automation scripts relying on `ed-telemetry tail` must continue functioning cleanly.
* **Unified Parity:** Flag behaviors (`-f` / `--follow`, `--json`, `--limit`) should behave consistently across related subcommands.

## Considered Options

* **Option 1: Status Quo.** Retain `tail` exclusively for SSE domain event streaming and `logs` for static snapshots.
* **Option 2: Destructive Rename.** Rename `tail` to `stream`, breaking all existing scripts and documentation.
* **Option 3: Canonical Alignment with Aliasing & `--follow` Parity.**
  * Introduce `ed-telemetry stream` as the primary subcommand for real-time domain event streaming.
  * Retain `ed-telemetry tail` as a fully supported alias for `stream`.
  * Add `-f` / `--follow` support to `ed-telemetry logs` to follow the rotating disk log file continuously (`tail -f`).
  * Add `-f` / `--follow` support to `ed-telemetry events` routing directly into the live event stream.

## Decision Outcome

Chosen Option: **Option 3: Canonical Alignment with Aliasing & `--follow` Parity**.

### Invariants & Invariant Rules

* **Invariant 1 (Subcommand Semantic Clarity):**
  * **`stream`:** Dedicated command for following the real-time multiplexed domain and audit event bus (`/api/v1/stream` SSE feed or standalone in-memory watcher queue).
  * **`tail`:** Preserved as a drop-in alias for `stream` to maintain backwards compatibility.
  * **`logs`:** Dedicated command for application diagnostic messages and errors. When invoked with `-f` / `--follow`, it continuously streams lines from `resolve_default_log_path()`.
  * **`events`:** Dedicated command for querying stored historical events in SQLite. When invoked with `-f` / `--follow`, it transparently dispatches to the live event stream.
* **Invariant 2 (Zero Third-Party Dependencies):** The continuous log file tailing in `logs -f` must be implemented using pure Python standard library filesystem polling (`time.sleep` and file pointer tracking) without external dependencies.
* **Invariant 3 (Diátaxis Integrity):** User-facing documentation in `docs/` will be updated strictly post-implementation to reflect `stream`, `logs -f`, and `events -f`.

---

## Positive Consequences

* Eliminates operator confusion between domain telemetry events and process debug traces.
* Satisfies expectations for standard log tailing via `ed-telemetry logs -f`.
* Preserves 100% backwards compatibility for existing deployments using `ed-telemetry tail`.

## Negative Consequences

* Minor code additions in `CliTelemetryAdapter` to support file pointer tracking for log streaming.
