---
title: "SDD 0038: Installer Post-Install Verification and Operator UX"
tags: ["sdd", "design", "installer", "health-check", "ux"]
created_at: "2026-11-15"
last_updated_at: "2026-11-15"
---

# SDD 0038: Installer Post-Install Verification and Operator UX

- **Status:** Approved for Implementation
- **Governing ADR:** [ADR 0044](../adr/0044_installer_post_install_verification_and_ux.md)

## 1. Implementation Plan

1. **Health Payload (`src/ed_telemetry/adapters/driving/api/server.py`):**
   - Add `"db": {"ok": True}` to `/api/v1/system/health` and `/api/v1/health` responses.
2. **Linux Installer (`packaging/linux/install.sh`):**
   - After `ed-telemetry service install`, poll `$HEALTH_URL` up to 10 times (0.5s apart).
   - If unreachable, print `journalctl --user -u ed-telemetry.service -n 20 --no-pager` guidance and exit `1`.
   - On success, print a summary banner with health payload, local (`http://127.0.0.1:8080`) and LAN (`http://<lan-ip>:8080`) URLs, `--allow-insecure` notice, and service management commands.

## 2. Verification Plan

- `bash -n packaging/linux/install.sh`
- `.venv/bin/python scripts/test_installers.py`
- `.venv/bin/pytest tests/unit/test_lockfile.py tests/unit/test_service_cli.py`
