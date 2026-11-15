---
title: "ADR 0044: Installer Post-Install Verification, Journal Discovery, and Operator UX"
tags: ["adr", "installer", "ux", "health-check", "journal-discovery"]
created_at: "2026-11-15"
last_updated_at: "2026-11-15"
---

# ADR 0044: Installer Post-Install Verification, Journal Discovery, and Operator UX

- **Status:** Proposed
- **Date:** 2026-11-15
- **Context:** `ed-telemetry` (`packaging/linux/install.sh`, `packaging/windows/ed-telemetry.iss`, `/api/v1/system/health`)

## 1. Context & Problem Statement

The `v1.0.6` installer successfully installs `ed-telemetry` and registers the OS background service, but exits immediately after `ed-telemetry service install` without verifying that the daemon actually started, bound its port, or located the Elite Dangerous journal directory.

## 2. Decision

Enhance the installer and post-install UX with three standard verification and reporting steps:

1. **Automated Post-Install Health Check:**
   - Poll `http://127.0.0.1:8080/api/v1/system/health` (e.g., up to 5–10 retries at 0.5s intervals) after `ed-telemetry service install`.
   - Fail loudly with service log instructions (`journalctl --user -u ed-telemetry.service`) if the daemon does not become healthy.
2. **Journal Directory Discovery & Reporting:**
   - Report whether the Elite Dangerous journal/snapshot directory was auto-discovered and readable (surfaced via `/api/v1/system/health` `journal_dir` metadata).
   - If not found (e.g., custom Steam/Proton prefix or Elite Dangerous not yet launched), display a non-fatal warning explaining how to set `ED_JOURNAL_DIR` or `--journal-dir`.
3. **Clear Post-Install Summary Banner:**
   - Display installed version, active local (`http://127.0.0.1:8080`) and LAN (`http://<lan-ip>:8080`) URLs, security mode (`--allow-insecure` notice), and quick management commands (`status`, `logs`, `uninstall`).

## 3. Consequences

- **Positive:** Users receive immediate confirmation that `ed-telemetry` is live, reachable on the LAN, and watching their journal directory—eliminating manual `curl` and `systemctl` checks.
- **Negative / Trade-offs:** Adds a 1–2 second post-install poll delay and requires `/api/v1/system/health` to surface resolved `journal_dir` path/readability.
