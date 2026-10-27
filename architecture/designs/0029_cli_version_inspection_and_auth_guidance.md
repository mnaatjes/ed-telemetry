---
title: "SDD-029: CLI Version Inspection and Actionable Authentication Guidance"
status: "approved"
date: "2026-10-27"
author: "Core Architecture Team"
governing_adr: "architecture/adr/0031_cli_version_inspection_and_auth_guidance.md"
tags: ["sdd", "cli", "ergonomics", "auth", "design"]
---

# SDD-029: CLI Version Inspection and Actionable Authentication Guidance

## 1. Executive Summary

This Software Design Document specifies the driving adapter enhancements required to fulfill [ADR 0031](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0031_cli_version_inspection_and_auth_guidance.md) and [Issue #84](https://github.com/mnaatjes/ed-telemetry/issues/84):
1. **Top-Level Version Resolution:** Exposing `-v` / `--version` flags on root `argparse.ArgumentParser`.
2. **Remediation Diagnostics in `auth show`:** Enhancing both human-readable text and JSON output to include concrete key generation commands when unauthenticated.

---

## 2. Component Design & Changes

### 2.1 Root Version Flag in `CliTelemetryAdapter._build_parser`

In `src/ed_telemetry/adapters/driving/cli/main.py`:
- Import `__version__` from `ed_telemetry`.
- Add argument to root parser:
  ```python
  parser.add_argument(
      "-v",
      "--version",
      action="version",
      version=f"%(prog)s {__version__}",
  )
  ```
- In `CliTelemetryAdapter.run()`, catch `SystemExit` from `action="version"` or `--help`, returning exit code `0` cleanly.

### 2.2 Remediation Diagnostics in `CliTelemetryAdapter._handle_auth_show`

When `token` is `None`:
1. **Human Output:**
   ```text
   No API Key configured (Local loopback unauthenticated mode).
   Credentials File: /path/to/credentials.json (Not Found)

   To generate and register an API key for network security:
     ed-telemetry auth keygen --register-env
   ```
2. **JSON Output (`--json`):**
   ```json
   {
     "api_key": null,
     "source": "none",
     "credentials_file": "/path/to/credentials.json",
     "credentials_file_exists": false,
     "remediation": "Run 'ed-telemetry auth keygen --register-env' to generate credentials."
   }
   ```
