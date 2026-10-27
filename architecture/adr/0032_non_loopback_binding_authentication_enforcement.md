---
title: "ADR 0032: Non-Loopback Network Binding Authentication Enforcement"
status: "accepted"
date: "2026-10-27"
deciders: ["Core Architecture Team"]
consulted: ["Issue #83", "ADR 0020", "ADR 0029"]
informed: ["All Engineers"]
tags: ["adr", "security", "perimeter", "network", "cli", "auth"]
---

# ADR 0032: Non-Loopback Network Binding Authentication Enforcement

## Context and Problem Statement

[ADR 0029](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0029_perimeter_network_guarding_and_storage_hardening.md) established pre-shared API keys and storage permissions hardening to protect telemetry data from untrusted network actors. However, if an operator launches the daemon across a LAN via `ed-telemetry serve --host 0.0.0.0` or a specific LAN IP without having generated an API key (`credentials.json` or `ED_API_KEY`), the server defaults to unauthenticated mode.

In this state, all endpoints (`/status`, `/events`, `/snapshots/*`, `/diagnostics/logs`) and the continuous Server-Sent Events stream (`/stream`) are exposed openly to any device on the local network. This violates the perimeter network defense invariant established in ADR 0029.

How should `ed-telemetry` prevent accidental unauthenticated LAN exposure while balancing developer agility and future satellite broadcast architectures ([ADR 0020](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0020_ingestion_scope_boundary_and_anti_creep_guardrails.md))?

## Decision Drivers

* **Fail-Safe Defaults (Saltzer & Schroeder Principle):** The default configuration must be secure; open network exposure must require intentional and explicit configuration.
* **Low Operator Friction for Local IPC:** Zero-friction unauthenticated operation must remain preserved for local loopback bindings (`127.0.0.1`, `localhost`, `::1`).
* **Direct LAN Ergonomics without Gateway Overhead:** Allow single-node operators and secondary devices (tablets, laptops) to query the daemon without immediately requiring an external proxy or dedicated `ed-broadcaster` daemon.
* **Zero Third-Party Dependencies:** Implement host validation using Python standard library constructs (`ipaddress`).

## Considered Options

* **Option 1: Status Quo.** Allow non-loopback bindings to operate unauthenticated if no API key is present. *(Rejected: High risk of silent telemetry and sensitive data exposure over local Wi-Fi).*
* **Option 2: Hard Lock to Loopback (`127.0.0.1` Only).** Forbid `--host` from binding to anything other than loopback, forcing all remote queries through future companion proxies (`ed-broadcaster` or SSH tunnels). *(Rejected: Adds excessive operational friction for common dual-screen desktop/laptop setups).*
* **Option 3: Loopback-by-Default with Strict Non-Loopback Enforcement.** Retain unauthenticated access on loopback interfaces, but require an established API key when binding to non-loopback interfaces (`0.0.0.0`, LAN IPs). Provide an explicit `--allow-insecure` flag for development or testing in isolated environments.

## Decision Outcome

Chosen Option: **Option 3: Loopback-by-Default with Strict Non-Loopback Enforcement**.

### Invariants & Compliance Rules

* **Invariant 1 (Loopback Exemption):** When `host` is determined to be a loopback address (`127.0.0.1`, `localhost`, `::1`, or IPv4 loopback subnet `127.0.0.0/8`), the daemon may operate in unauthenticated mode if no API key is configured.
* **Invariant 2 (Non-Loopback Fail-Fast Gate):** When `host` is non-loopback (e.g. `0.0.0.0`, `192.168.x.x`), the daemon MUST fail fast on startup with POSIX exit code `1` and actionable remediation unless:
  1. A valid API key is resolved (via `--api-key`, `ED_API_KEY`, or `credentials.json`), OR
  2. The operator explicitly passes `--allow-insecure`.
* **Invariant 3 (Prominent Security Warning on Insecure Override):** When `--allow-insecure` is active on a non-loopback host, the daemon must emit a conspicuous warning banner to `stderr`/`stdout` confirming that the network perimeter is unauthenticated.

## Positive Consequences

* Eliminates silent, accidental leakage of telemetry events, cockpit coordinates, and Commander persona names over home networks.
* Provides clear, self-contained terminal remediation commands when startup is aborted.
* Preserves seamless local desktop development without requiring manual API key generation.
* Retains compatibility with future satellite broadcasting daemons (`ed-broadcaster`) which can consume `127.0.0.1` locally.
