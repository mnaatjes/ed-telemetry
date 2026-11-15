---
title: "Tutorial: Installing ed-telemetry as a Background Service"
tags: ["tutorial", "diataxis", "installation", "service"]
created_at: "2026-11-15"
last_updated_at: "2026-11-15"
---

# Tutorial: Installing `ed-telemetry` as a Background Service

This tutorial walks through installing `ed-telemetry` (`v1.0.0+`) as a persistent, single-instance host daemon on Linux or Windows.

## 1. Linux / SteamOS

1. Run the idempotent installer script:

   ```bash
   bash packaging/linux/install.sh
   ```

2. Verify the service is running:

   ```bash
   curl -s http://127.0.0.1:8080/api/v1/system/health
   ```

   You should receive `{"status": "ok", "service": "ed-telemetry", "version": "1.0.0", ...}`.

## 2. Windows

1. Download and run `ed-telemetry-setup.exe` from the GitHub Release (built from `packaging/windows/ed-telemetry.iss`).
2. The installer places `ed-telemetry.exe` in `%LOCALAPPDATA%\Programs\ed-telemetry` and registers the `ed-telemetry` logon task (`ed-telemetry serve --host 0.0.0.0 --allow-insecure`).

## 3. Managing the Service

- Check status: `systemctl --user status ed-telemetry.service` (Linux) or `schtasks /Query /TN ed-telemetry` (Windows).
- Stop / Uninstall: use `control_service("stop")` / `control_service("uninstall")` via `ed_telemetry.adapters.driving.cli.service`.
