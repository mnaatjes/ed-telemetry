---
title: "ADR 0029: Perimeter Network Guarding, Storage Hardening, and Sensitive Telemetry Controls"
status: "accepted"
date: "2026-10-26"
decision_makers: ["Core Architecture Team"]
consulted: ["Security & Sensitive Data Leakage Audit (#77)", "Outside-In Threat Model (#78)"]
informed: ["All Contributors"]
tags: ["adr", "security", "privacy", "permissions", "api-key", "cors", "pii"]
---

# ADR 0029: Perimeter Network Guarding, Storage Hardening, and Sensitive Telemetry Controls

## Context and Problem Statement

A security and sensitive data leakage audit ([Issue #77](https://github.com/mnaatjes/ed-telemetry/issues/77)) and outside-in threat model ([Issue #78](https://github.com/mnaatjes/ed-telemetry/issues/78)) identified four exposure vectors in `ed-telemetry`:
1. **Unauthenticated Network Binding:** When serving over `0.0.0.0`, all REST and SSE endpoints respond without credential verification, allowing arbitrary LAN devices to stream gameplay events, Commander financial balances, and active coordinates.
2. **Wildcard Cross-Origin Resource Sharing (CORS):** The HTTP server hardcodes `Access-Control-Allow-Origin: *`, allowing untrusted third-party websites visited in a Commander's browser to harvest live telemetry via background `fetch()` calls.
3. **Insecure Multi-User Filesystem Permissions:** Default umasks create database and log directories (`~/.local/share/ed-telemetry/` and `~/.local/state/ed-telemetry/`) as world-readable (`0755` / `0644`), exposing SQLite records to co-located non-privileged accounts.
4. **Sensitive Payload Exposure:** Frontier Customer IDs (`FID`), Commander persona names, in-game direct player messages (`ReceiveText`), and host system paths are exposed over unauthenticated transport feeds.

How should `ed-telemetry` harden its local persistence and network transports without violating the zero-dependency pure ingestion boundary ([ADR 0020](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0020_ingestion_scope_boundary_and_anti_creep_guardrails.md)) or breaking downstream satellite tools?

## Decision Drivers

* **Zero Scope Creep (ADR 0020):** Retain domain agnosticism and zero external dependencies. Do not embed heavy encryption frameworks (e.g. SQLCipher, PyWin32).
* **Downstream Innovation Compatibility:** Do not permanently strip ("frag") `FID`, Commander names, or comms at the ingestion or SQLite persistence layer; downstream personal sync tools (Inara, CAPI) and messaging overlays depend on these values.
* **Perimeter Defense:** Treat the network transport as the true security perimeter rather than over-engineering application-layer field encryption.
* **Operator Ergonomics:** Provide zero-friction local-trusted defaults (`127.0.0.1`) while providing clean, pre-shared key credentials for network-exposed deployments.

## Considered Options

* **Option 1: Status Quo.** Leave endpoints unauthenticated with wildcard CORS and default umask permissions.
* **Option 2: Ingestion-Level Data Fragging & Field-Level Encryption.**
  * Strip `FID`, `ReceiveText`, and player names at the watcher layer, or encrypt individual JSON fields before writing to SQLite.
  * *Rejected:* Breaks downstream personal sync adapters (Inara, CAPI), chat apps, and historical replays. Introduces key distribution complexity.
* **Option 3: Perimeter Network Guarding, Storage Hardening, and Path Masking.**
  * Enforce POSIX `chmod 0700` (directory) and `0600` (database/log files) on Unix hosts.
  * Introduce Pre-Shared API Key authentication (`--api-key`, `ED_API_KEY`, and canonical `credentials.json`) on HTTP/SSE endpoints.
  * Restrict CORS to local development origins by default, with configurable allowed origins (`--cors-origin`).
  * Mask host system paths (`/home/michael/...` $\rightarrow$ `~/...`) in public status serializers.

## Decision Outcome

Chosen Option: **Option 3: Perimeter Network Guarding, Storage Hardening, and Path Masking**.

### Invariants & Invariant Rules

* **Invariant 1 (Local Storage Permission Masking):**
  * Under POSIX environments, `SqlitePersistenceManager` and rotating log handlers must strictly enforce `0700` permissions on parent directories and `0600` on database (`telemetry.db*`) and log files (`ed-telemetry.log*`).
  * Under Windows NTFS, reliance is placed on native `%LOCALAPPDATA%` user ACL inheritance (no external dependencies).
* **Invariant 2 (Perimeter API Key Enforcement):**
  * When `--api-key <token>` or `ED_API_KEY` is configured, all HTTP REST routes and `/api/v1/stream` require authentication via `Authorization: Bearer <token>`, `X-API-Key: <token>`, or query parameter `?api_key=<token>` (for browser `EventSource` compatibility).
  * Unauthorized requests must be rejected immediately with `HTTP 401 Unauthorized` and an RFC 7807 problem details JSON payload.
  * Constant-time comparison (`hmac.compare_digest`) must be used for token validation.
* **Invariant 3 (Prefixed CSPRNG Token Format, Credential Precedence & Leak Detection):**
  * **Token Cryptographic Standard:** API keys generated via `ed-telemetry auth keygen` must not rely on predictable hashing of system attributes. They must be derived from kernel-level CSPRNG entropy (`secrets.token_hex(24)`) formatted with the canonical prefix `ed_sec_` (e.g., `ed_sec_9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b`, providing 192+ bits of entropy).
  * **Automated Leak Detection:**
    * Include a custom regex pattern (`\bed_sec_[a-fA-F0-9]{48}\b`) in test suites (`tests/architecture/test_boundaries.py` and downstream verification runners) to ensure tokens are never logged or committed.
    * Provide pattern definition for repository secret scanning (e.g. GitHub Secret Scanning / GitGuardian custom pattern compatibility).
  * Key resolution hierarchy: Explicit CLI flag $\rightarrow$ Environment variable (`ED_API_KEY`) $\rightarrow$ Canonical credentials file (`~/.config/ed-telemetry/credentials.json` or `%LOCALAPPDATA%`) $\rightarrow$ Unauthenticated local mode.
  * The CLI will provide `ed-telemetry auth keygen`, `show`, `revoke`, and automated environment registration utilities:
    * **Linux / Unix (`--register-env`):** Safely appends `export ED_API_KEY="<token>"` to the user's active shell configuration (`~/.bashrc` or `~/.zshrc`) with idempotency guards.
    * **Windows (`--register-env`):** Persists `ED_API_KEY` into the Windows User Environment table via PowerShell (`[Environment]::SetEnvironmentVariable`) or native `setx` without requiring administrative elevation.
* **Invariant 4 (CORS Origin Restriction):**

  * Replace `Access-Control-Allow-Origin: *` with strict loopback validation (`localhost`, `127.0.0.1`, `[::1]`).
  * Support explicit operator origin whitelisting via `--cors-origin` / `ED_CORS_ORIGIN`.
* **Invariant 5 (Host Path Sanitization):**
  * All public API endpoints (`/status`, `/status/game`, `telemetry.audit`) must sanitize host user directory prefixes before emitting JSON.
* **Invariant 6 (Lossless Raw Persistence):**
  * The core ingestion engine and SQLite database must retain lossless raw telemetry events (including `FID`, Commander, `ReceiveText`, and `Friends`) to ensure downstream sync adapters retain full fidelity.

---

## Positive Consequences

* Fully addresses security vulnerabilities identified in Issue #77 and Issue #78.
* Prevents cross-site telemetry harvesting from malicious browser scripts.
* Protects multi-user local machines from unauthorized database snooping.
* Preserves 100% compatibility with future downstream personal sync tools (Inara, CAPI) and chat overlays.
* Zero external third-party dependencies required.

## Negative Consequences

* Remote clients connecting across a LAN to `0.0.0.0` must supply an API key when key enforcement is enabled.
