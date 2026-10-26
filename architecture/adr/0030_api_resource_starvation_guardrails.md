---
title: "ADR 0030: API Resource Starvation Guardrails and Concurrency Throttling"
status: "accepted"
date: "2026-10-26"
deciders: ["Core Architecture Team"]
consulted: ["Security & Telemetry Working Group"]
informed: ["All Engineers"]
tags: ["adr", "security", "guardrails", "sse", "rate-limiting", "dos"]
---

# ADR 0030: API Resource Starvation Guardrails and Concurrency Throttling

## Context and Problem Statement

Following the completion of perimeter authentication and storage hardening in [ADR 0029](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0029_perimeter_network_guarding_and_storage_hardening.md), an evaluation of [Issue #78](https://github.com/mnaatjes/ed-telemetry/issues/78) highlighted two residual resource exhaustion vectors:
1. **Unbounded Query Allocation:** Endpoints accepting query parameters (`/api/v1/events` and `/api/v1/diagnostics/logs`) parsed `?limit=` directly as an unbounded integer. A request with `?limit=10000000` forces the daemon to allocate massive SQLite or memory buffers, triggering OOM crashes.
2. **Unbounded SSE Thread Starvation:** The daemon utilizes Python's standard library `ThreadingHTTPServer`, where each persistent connection to `/api/v1/stream` consumes an OS-level thread. A client rapidly opening dozens of SSE streams can exhaust thread pools and file descriptors, starving other REST API operations.

How should `ed-telemetry` protect itself against accidental or intentional resource exhaustion without introducing third-party framework dependencies?

## Decision Drivers

* **Zero External Dependencies:** Adhere strictly to [ADR 0020](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0020_ingestion_scope_boundary_and_anti_creep_guardrails.md) by implementing all controls using Python standard library primitives (`threading.Lock`, RFC 7807 problem details).
* **Deterministic Bounds:** Ensure that no query parameter can cause memory allocations exceeding safe operational ceilings.
* **Graceful Degradation:** Inform clients with standardized HTTP status codes (`HTTP 429 Too Many Requests`) when capacity limits are reached.

## Considered Options

* **Option 1: Uncapped (Status Quo)** — Trust clients and rely on OS memory limits. (Rejected: Vulnerable to DoS and OOM).
* **Option 2: Third-Party Rate Limiter Framework** — Introduce `slowapi` or `limits` with Redis backend. (Rejected: Violates stdlib-only constraint).
* **Option 3: In-Memory Bounded Clamping and Atomic SSE Connection Limiting** — Enforce clamped integer limits on paginated queries and maintain an atomic active-client counter for SSE streams.

## Decision Outcome

Chosen Option: **Option 3: In-Memory Bounded Clamping and Atomic SSE Connection Limiting**.

### Positive Consequences
* Prevents memory bloat by clamping any supplied `limit` query parameter to `max(1, min(limit, 500))`.
* Protects daemon thread pools by enforcing a hard ceiling on concurrent `/api/v1/stream` listeners (default `max_sse_clients = 16`).
* When the SSE limit is exceeded, rejects incoming connection requests immediately with `HTTP 429 Too Many Requests` and RFC 7807 problem details JSON.
* Retains pure Python standard library design with zero external dependencies.

### Negative Consequences
* Clients requesting more than 500 records at once must paginate using `since_id`.
* Environments with more than 16 simultaneous stream subscribers must adjust `max_sse_clients` in adapter configuration.

## Invariants & Compliance Rules

* **Invariant 1 (Query Clamping):** Any handler parsing a `limit` query parameter must clamp the resulting integer:
  $$\text{effective\_limit} = \max(1, \min(\text{requested\_limit}, 500))$$
* **Invariant 2 (Atomic SSE Concurrency Tracking):** The HTTP driving adapter must track active SSE streaming threads using a thread-safe atomic counter.
* **Invariant 3 (RFC 7807 Conformance on Rejection):** An rejected SSE connection must return `HTTP 429 Too Many Requests` with `application/problem+json`:
  ```json
  {
    "type": "about:blank",
    "title": "Too Many Requests",
    "status": 429,
    "detail": "Maximum concurrent SSE stream limit reached (16 clients).",
    "instance": "/api/v1/stream"
  }
  ```
