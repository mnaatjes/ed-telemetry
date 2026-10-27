---
title: "ADR 0031: CLI Version Inspection and Actionable Authentication Guidance"
status: "accepted"
date: "2026-10-27"
deciders: ["Core Architecture Team"]
consulted: ["Issue #84", "Security & Telemetry Working Group"]
informed: ["All Engineers"]
tags: ["adr", "cli", "ergonomics", "qol", "auth"]
---

# ADR 0031: CLI Version Inspection and Actionable Authentication Guidance

## Context and Problem Statement

During operational deployment and multi-host validation across Linux and remote machines ([Issue #84](https://github.com/mnaatjes/ed-telemetry/issues/84)), two CLI ergonomic gaps were identified:
1. **Missing Top-Level Version Inspection:** Invoking `ed-telemetry --version` or `ed-telemetry -v` produces an `argparse` rejection (`unrecognized arguments: --version`), forcing operators to inspect Python package metadata or pipx lists manually.
2. **Passive Unauthenticated Auth Status:** Running `ed-telemetry auth show` in unauthenticated mode outputs diagnostic statements without actionable remediation guidance explaining how to generate or configure an API key.

## Decision Drivers

* **Zero External Dependencies ([ADR 0020](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0020_ingestion_scope_boundary_and_anti_creep_guardrails.md)):** Use standard library `argparse` built-in `action="version"`.
* **Standard CLI Ergonomics (POSIX & GNU Standards):** Support `-v` and `--version` flags on root command invocations.
* **Actionable Operator Diagnostics ([ADR 0025](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0025_cli_hybrid_ipc_and_persistence_anchoring.md)):** Provide immediate next-action commands whenever an operator inspects unauthenticated credentials.

## Considered Options

* **Option 1: Status Quo.** Keep version unexposed in CLI and maintain passive `auth show` status reporting.
* **Option 2: Dedicated `version` Subcommand.** Introduce `ed-telemetry version`. (Rejected: Fails standard Unix convention for `--version` flags).
* **Option 3: Top-Level `action="version"` and Remediation-Augmented `auth show`.** Wire root parser `-v`/`--version` to `ed_telemetry.__version__` and provide step-by-step registration instructions in `auth show`.

## Decision Outcome

Chosen Option: **Option 3: Top-Level `action="version"` and Remediation-Augmented `auth show`**.

### Invariants & Invariant Rules

* **Invariant 1 (Root Version Flags):** `ed-telemetry` must support `-v` and `--version` as top-level arguments, outputting `ed-telemetry <version>` to `stdout` and exiting with code `0`.
* **Invariant 2 (Actionable Auth Guidance):** When `ed-telemetry auth show` is executed and no API key is resolved:
  * Human text mode must print concrete steps to generate credentials via `ed-telemetry auth keygen --register-env` or set `ED_API_KEY`.
  * JSON mode (`--json`) must include a `"remediation"` property detailing recommended action commands.

## Positive Consequences

* Immediate visibility of installed software release on target hosts.
* Self-documenting credential setup instructions directly in the terminal without consulting external runbooks.
