---
title: "ADR 0033: Dynamic Credential Hot-Reloading via File MTime Watch"
status: "accepted"
date: "2026-10-27"
deciders: ["Core Architecture Team"]
consulted: ["Issue #89", "Issue #90", "ADR 0029", "ADR 0032"]
informed: ["All Engineers"]
tags: ["adr", "security", "perimeter", "auth", "credentials", "hot-reload"]
---

# ADR 0033: Dynamic Credential Hot-Reloading via File MTime Watch

## Context and Problem Statement

[ADR 0029](0029_perimeter_network_guarding_and_storage_hardening.md) and [ADR 0032](0032_non_loopback_binding_authentication_enforcement.md) established pre-shared API keys and storage hardening to protect telemetry feeds over non-loopback network interfaces.

However, in the initial implementation, `HttpApiAdapter.start()` captured the resolved API key as an immutable string and injected it into the dynamic request handler class (`TelemetryHttpHandler.server_api_key`). When an operator regenerated an API key using `ed-telemetry auth keygen --force`, the credentials file (`credentials.json`) was updated on disk, but the running daemon process retained the stale in-memory token. Subsequent client requests using the newly generated key failed with `HTTP 401 Unauthorized` until the daemon process was manually killed and restarted (Issue #89).

How should `ed-telemetry` synchronize credential updates between client commands and the running background daemon without requiring disruptive process restarts or adding heavy IPC infrastructure?

## Decision Drivers

* **Zero-Downtime Key Rotation:** Operators must be able to rotate compromised or stale API keys (`auth keygen --force`) without interrupting active telemetry ingestion or terminating running daemon instances.
* **Deterministic Precedence:** Maintain the established configuration hierarchy: explicit CLI flag (`--api-key`) > environment variable (`ED_API_KEY`) > stored credential file (`credentials.json`).
* **Static Override Immutability:** When an explicit `--api-key <override>` CLI flag was passed at server startup, that static override must remain pinned and immune to disk modifications.
* **Hexagonal Boundary Purity:** Domain and application services must remain completely agnostic of HTTP authentication tokens and filesystem credential structures. Credential tracking must remain strictly confined to driving adapters (`adapters/driving/api` and `adapters/driving/cli`).
* **Zero Additional External Dependencies:** Credential change detection must leverage standard library filesystem metadata (`os.stat().st_mtime_ns`) without introducing third-party file-watching daemons.

## Considered Options

* **Option 1: Require Daemon Restart on Key Rotation.** Mandate that `ed-telemetry auth keygen --force` terminates existing daemons or forces the operator to manually restart `ed-telemetry serve`. *(Rejected: Disruptive to ongoing game telemetry recording; fails to handle headless or background services gracefully).*
* **Option 2: POSIX Signal Handler (`SIGHUP`).** Register a `SIGHUP` signal handler on the daemon process to trigger credential file re-reading. *(Rejected: Platform-dependent; does not function natively on Windows NT without Wine or specialized emulation).*
* **Option 3: Dynamic Credential Provider with File Modification-Time (`mtime`) Watch (Pattern A).** Inject a callable credential provider `Callable[[], str | None]` into `HttpApiAdapter`. The provider checks `st_mtime_ns` of `credentials.json` on incoming requests (or when a cached timestamp expires). If modified, it dynamically reloads the token from disk into memory.

## Decision Outcome

Chosen Option: **Option 3: Dynamic Credential Provider with File Modification-Time (`mtime`) Watch (Pattern A)**.

### Architectural Invariants & Mechanics

* **Invariant 1 (Dynamic Evaluation):** The HTTP request handler must evaluate credentials against a dynamic provider `Callable[[], str | None]` rather than an immutable static string, unless explicitly pinned via CLI argument.
* **Invariant 2 (Static Flag Precedence & Pinning):** If `--api-key <token>` was passed explicitly at `ed-telemetry serve` launch, the provider returns that static token unconditionally, bypassing filesystem checks.
* **Invariant 3 (Efficient MTime Caching):** When tracking `credentials.json`, the provider samples `os.stat().st_mtime_ns`. It re-reads the JSON payload from disk only when the file modification timestamp has changed since the previous read, avoiding unneeded disk I/O on high-frequency HTTP/SSE queries.
* **Invariant 4 (Environment Variable Precedence):** If `ED_API_KEY` is present in the daemon's runtime environment, it takes precedence over `credentials.json` but is subject to static evaluation unless unset.
* **Invariant 5 (Graceful Handling of Revocation / Deletion):** If `credentials.json` is deleted or revoked (`ed-telemetry auth revoke`), the provider dynamically returns `None`, transitioning non-loopback bindings to reject unauthenticated requests or loopback bindings to local unauthenticated mode as governed by ADR 0032.

## Positive Consequences

* API key rotation via `ed-telemetry auth keygen --force` takes effect daemon-wide immediately without restarting the background service.
* Cross-platform consistency across Linux, Steam Proton, and Windows NT without platform-specific signals.
* Preserves high request throughput via zero-allocation `st_mtime_ns` cache checks.
