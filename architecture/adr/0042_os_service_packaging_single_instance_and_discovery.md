---
title: "ADR 0042: OS Service Packaging, Single-Instance Guard, and LAN Discovery"
tags: ["adr", "architecture", "packaging", "installer", "service", "discovery"]
created_at: "2026-11-15"
last_updated_at: "2026-11-15"
---

# ADR 0042: OS Service Packaging, Single-Instance Guard, and LAN Discovery

- **Status:** Proposed
- **Date:** 2026-11-15
- **Context:** `ed-telemetry` (`v0.12.1` -> production host daemon)

## 1. Context & Problem Statement

`ed-telemetry` serves as the single-producer host daemon for Elite Dangerous journal and status telemetry, consumed over HTTP/SSE by one or more downstream `ed-fleet-client` applications (either on the same host or across a LAN).

Currently (`v0.12.1`), `ed-telemetry` has a zero-dependency Python core, a CLI entry point (`ed-telemetry`), and `/api/v1/system/health` + `/api/v1/health` endpoints. To support seamless installation and multi-app orchestration for both developers and non-technical end users, five operational gaps must be addressed.

## 2. Decision

Adopt the following five capabilities as the target production packaging and runtime contract for `ed-telemetry`:

1. **OS Service / Background Daemonization:**
   - Provide `ed-telemetry service install|start|stop|status` subcommands.
   - Support a `systemd --user` unit template on Linux/SteamOS and Windows Service / Task Scheduler / Tray registration on Windows so the daemon starts automatically on login.
2. **Cross-Platform Installers (Windows & Linux):**
   - **Windows:** Provide a frozen executable build (PyInstaller/Nuitka) and a Windows installer (Inno Setup / MSIX) published via GitHub Releases, enabling one-click installation without requiring Python or `uv`.
   - **Linux (Steam Proton / Wine / SteamOS):** Provide an AppImage / `.deb` / `.rpm` or single-line `install.sh` (`uv tool install` + `systemctl --user enable --now ed-telemetry`) for non-technical Linux users.
3. **Single-Instance Guard:**
   - Enforce a PID/lockfile and clean port-in-use check so bundled downstream app installers or launchers can detect an already-running `ed-telemetry` instance and reuse it without conflict.
4. **Rich Health & Compatibility Payload:**
   - Expand `/api/v1/system/health` (and `/api/v1/health`) to include `"version": __version__` and `"journal_dir"` readiness status so `ed-fleet-client` (`ed-fleet doctor`) can verify API compatibility and journal availability.
5. **Split-Host Binding & Discovery:**
   - Document and expose LAN binding (`--host 0.0.0.0` / config) alongside optional mDNS/Zeroconf advertisement (`_ed-telemetry._tcp.local.`) so remote `ed-fleet-client` apps can auto-discover the gaming PC.

### 2.1 Idempotent 4-Step Installer Workflow

Both standalone and bundled installers follow the same idempotent workflow:
1. **Probe:** Check if `ed-telemetry` is already running (`/api/v1/system/health`) or if its lockfile/service is registered. If running, exit `0` and reuse the existing instance.
2. **Install Binary/Package:** Place the frozen binary (Windows `.exe` / Linux binary or `uv tool`) in the OS-standard application directory.
3. **Register Service:** Invoke `ed-telemetry service install` (which writes the Windows Service/Task or `systemd --user` unit).
4. **Start & Verify:** Invoke `ed-telemetry service start` and poll `/api/v1/system/health` until `200 OK`.

Steps 3 and 4 belong to the `ed-telemetry` package itself (`ed-telemetry service ...`), while steps 1 and 2 are executed by the OS installer.

### 2.2 Repository Layout

Installers are build/distribution artifacts, not runtime hexagonal adapters:
- **Runtime service CLI (`ed-telemetry service install|start|stop|status`):** Lives inside `src/ed_telemetry/adapters/driving/cli/`.
- **OS Installer & Packaging Definitions:** Live in a top-level `packaging/` directory alongside `scripts/` and `.github/workflows/release.yml`:

```text
packaging/
├── windows/   # PyInstaller .spec + Inno Setup (.iss)
└── linux/     # systemd user unit template + .deb / AppImage / install.sh
```

## 3. Consequences

- **Positive:**
  - Multiple downstream applications can safely share a single `ed-telemetry` host daemon without filesystem or port contention.
  - Non-technical Windows and Linux users can install `ed-telemetry` standalone or via a bundled app installer in one step.
  - Split-host deployments (e.g., Windows gaming PC + Linux/tablet dashboard) gain zero-config discovery and version verification.
- **Negative / Trade-offs:**
  - Introduces platform-specific service wrappers (Windows vs. Linux `systemd`) and release-pipeline build steps for frozen binaries.
