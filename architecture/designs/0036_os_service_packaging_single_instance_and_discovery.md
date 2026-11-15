---
title: "SDD 0036: OS Service Packaging, Single-Instance Guard, and LAN Discovery"
tags: ["sdd", "design", "packaging", "installer", "service", "discovery"]
created_at: "2026-11-15"
last_updated_at: "2026-11-15"
---

# SDD 0036: OS Service Packaging, Single-Instance Guard, and LAN Discovery

- **Status:** Proposed
- **Governing ADR:** [ADR 0042](../adr/0042_os_service_packaging_single_instance_and_discovery.md)
- **Target Version:** `ed-telemetry` `0.13.0`

## 1. Scope & Implementation Plan

### 1.1 Rich Health & Compatibility Payload
- **Target:** `src/ed_telemetry/adapters/driving/api/server.py`
- **Change:** Expand `/api/v1/system/health` and `/api/v1/health` JSON responses to include:
  - `"status": "ok"`
  - `"service": "ed-telemetry"`
  - `"version": __version__`
  - `"journal_dir": {"path": str(...), "exists": bool, "readable": bool}`
- **API Contract:** Update `architecture/api/` OpenAPI YAML to document the new health response fields.

### 1.2 Single-Instance Guard
- **Target:** `src/ed_telemetry/bootstrap/lockfile.py` (new) + `src/ed_telemetry/bootstrap/container.py`
- **Change:**
  - Acquire an OS-appropriate PID/lockfile (e.g., `~/.local/share/ed-telemetry/ed-telemetry.pid` on Linux, `%LOCALAPPDATA%\ed-telemetry\ed-telemetry.pid` on Windows) on daemon startup.
  - If an active instance is already running (PID alive or `/api/v1/system/health` responds on configured port), log a clear message and exit cleanly (`0` for `service start`, non-zero for conflicting foreground start).

### 1.3 OS Service CLI (`ed-telemetry service`)
- **Target:** `src/ed_telemetry/adapters/driving/cli/service.py` (new) + `src/ed_telemetry/adapters/driving/cli/main.py`
- **Subcommands:**
  - `ed-telemetry service install`: Writes and enables `systemd --user` unit (`~/.config/systemd/user/ed-telemetry.service`) on Linux, or registers Windows Scheduled Task / Service on Windows.
  - `ed-telemetry service start|stop|status|uninstall`: Delegates to `systemctl --user` (Linux) or `schtasks`/`sc` (Windows).

### 1.4 Split-Host Binding & mDNS Discovery
- **Target:** `src/ed_telemetry/bootstrap/container.py` + `src/ed_telemetry/adapters/driving/api/discovery.py` (new)
- **Change:**
  - Support `--host 0.0.0.0` (and `ED_TELEMETRY_HOST`) for LAN binding.
  - Add optional mDNS/Zeroconf advertisement (`_ed-telemetry._tcp.local.`) publishing `version` and `port` TXT records when `--discoverable` is enabled.

### 1.5 Cross-Platform Installers (`packaging/`)
- **Target:** Top-level `packaging/` directory:
  - `packaging/windows/`: PyInstaller `.spec` + Inno Setup `.iss` implementing the idempotent 4-step workflow (Probe -> Install -> `ed-telemetry service install` -> `ed-telemetry service start` + health poll).
  - `packaging/linux/`: `ed-telemetry.service` template + `install.sh` (`uv tool install` + `systemctl --user enable --now ed-telemetry`).

### 1.6 Post-Implementation Documentation (Diataxis)
- Author/update `docs/tutorials/`, `docs/how-to/`, `docs/reference/`, and `docs/explanation/` covering installation, service management, LAN discovery, and the single-producer / multi-consumer architecture.

## 2. Testing & Verification Plan

1. **Unit Tests (`tests/unit/`):**
   - `test_health_payload.py`: Verify `/api/v1/system/health` includes `version` and `journal_dir` fields.
   - `test_lockfile.py`: Verify single-instance lock acquisition, stale PID cleanup, and conflict detection.
   - `test_service_cli.py`: Mock `subprocess.run` to verify `ed-telemetry service install|start|stop|status` generates valid `systemd --user` and Windows commands.
2. **Integration Tests (`tests/integration/`):**
   - Start `ed-telemetry` on an ephemeral port, probe `/api/v1/system/health`, and verify second-instance guard behavior.
3. **Quality Gates:**
   - `pytest`, `ruff check .`, `mypy src/`, and `import-linter` must all pass.
