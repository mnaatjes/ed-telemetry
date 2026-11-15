---
title: "SDD 0037: Linux Standalone Bundle and Self-Bootstrapping Installer"
tags: ["sdd", "packaging", "linux", "pyinstaller", "ci"]
created_at: "2026-11-15"
last_updated_at: "2026-11-15"
---

# SDD 0037: Linux Standalone Bundle and Self-Bootstrapping Installer

- **Status:** Approved for Implementation
- **Governing ADR:** [ADR 0043](../adr/0043_linux_standalone_bundle_and_release_pipeline.md)

## 1. Implementation Plan

1. **`packaging/linux/ed-telemetry.spec`:**
   - PyInstaller one-file spec targeting `src/ed_telemetry/bootstrap/container.py` with `name='ed-telemetry'` and `pathex=['src']`.
2. **`packaging/linux/install.sh`:**
   - Probe `http://127.0.0.1:8080/api/v1/system/health`; exit `0` if already running.
   - Try downloading `https://github.com/mnaatjes/ed-telemetry/releases/latest/download/ed-telemetry-linux-x86_64.tar.gz` into `~/.local/bin/ed-telemetry`.
   - Fallback: if download fails (e.g., pre-release), install `uv` if missing and run `uv tool install --upgrade git+https://github.com/mnaatjes/ed-telemetry.git`.
   - Ensure `~/.local/bin` is on `PATH` and run `ed-telemetry service install`.
3. **`.github/workflows/release-linux.yml`:**
   - Trigger on `push: tags: ['v*']`.
   - Build `dist/ed-telemetry` via PyInstaller, archive as `ed-telemetry-linux-x86_64.tar.gz`, and upload to the GitHub Release via `softprops/action-gh-release@v2`.

## 2. Verification Plan

- `bash -n packaging/linux/install.sh` (syntax check).
- `pytest` and `ruff check .` pass.
