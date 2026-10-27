---
title: "SDD-030: Non-Loopback Network Binding Authentication Enforcement"
status: "approved"
date: "2026-10-27"
author: "Core Architecture Team"
governing_adr: "architecture/adr/0032_non_loopback_binding_authentication_enforcement.md"
tags: ["sdd", "security", "perimeter", "network", "cli", "auth", "design"]
---

# SDD-030: Non-Loopback Network Binding Authentication Enforcement

## 1. Executive Summary

This Software Design Document specifies the technical changes required in the CLI driving adapter (`CliTelemetryAdapter`) to enforce the perimeter authentication invariants defined in [ADR 0032](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0032_non_loopback_binding_authentication_enforcement.md) and [Issue #83](https://github.com/mnaatjes/ed-telemetry/issues/83):
1. **Loopback Classification:** Deterministic classification of network binding targets as loopback vs. non-loopback.
2. **Pre-flight Security Gate:** Halting daemon initialization with exit code `1` if non-loopback binding is attempted without an API key and without explicit insecure override.
3. **CLI Ergonomics:** Adding `--allow-insecure` to the `serve` subcommand.

---

## 2. Technical Design & Component Changes

### 2.1 Loopback Host Evaluator (`is_loopback_host`)

In `src/ed_telemetry/adapters/driving/cli/main.py`, a helper evaluates whether a host string is restricted to the local machine:

```python
import ipaddress


def is_loopback_host(host: str) -> bool:
    """Determine whether a host string represents a loopback interface."""
    host_clean = host.strip().lower()
    if host_clean in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        ip = ipaddress.ip_address(host_clean)
        return ip.is_loopback
    except ValueError:
        return False
```

Note: `0.0.0.0` and `::` (unspecified addresses) evaluate to `is_loopback = False`, correctly classifying them as non-loopback bindings.

---

### 2.2 CLI Argument Definition in `_build_parser`

Under `serve_parser`:
```python
serve_parser.add_argument(
    "--allow-insecure",
    action="store_true",
    help="Explicitly permit unauthenticated access on non-loopback network interfaces",
)
```

---

### 2.3 Enforcement Gate in `_handle_serve`

Before starting stream processing or socket listening:
```python
is_loopback = is_loopback_host(args.host)
allow_insecure = getattr(args, "allow_insecure", False)

if not is_loopback and not resolved_key and not allow_insecure:
    sys.stderr.write(
        f"[SECURITY ERROR] Refusing to bind to non-loopback host '{args.host}' without authentication.\n"
        "All telemetry streams and endpoints would be accessible unauthenticated to network peers.\n\n"
        "Remediation:\n"
        "  1. Generate and register an API key: ed-telemetry auth keygen --register-env\n"
        f"  2. Or pass an API key directly:      ed-telemetry serve --host {args.host} --api-key <TOKEN>\n"
        f"  3. Or explicitly permit insecure:    ed-telemetry serve --host {args.host} --allow-insecure\n"
    )
    return 1, {
        "error": "Refusing to bind to non-loopback interface without authentication",
        "host": args.host,
    }
```

If `allow_insecure` is active on non-loopback:
```python
if not is_loopback and not resolved_key and allow_insecure:
    print("[WARNING] SECURITY RISK: Running on non-loopback host in unauthenticated mode.")
    print("          All telemetry endpoints are openly accessible to network peers.")
```
