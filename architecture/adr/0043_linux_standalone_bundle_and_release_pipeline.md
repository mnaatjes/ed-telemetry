---
title: "ADR 0043: Linux Standalone Executable Bundle and Release Pipeline"
tags: ["adr", "packaging", "linux", "pyinstaller", "release"]
created_at: "2026-11-15"
last_updated_at: "2026-11-15"
---

# ADR 0043: Linux Standalone Executable Bundle and Release Pipeline

- **Status:** Proposed
- **Date:** 2026-11-15
- **Context:** `ed-telemetry` (`packaging/linux/`)

## 1. Context & Problem Statement

Currently, `packaging/linux/install.sh` assumes `uv` is pre-installed on the target Linux host. Non-technical users on SteamOS or desktop Linux who do not have `uv` or Python 3.11+ installed hit a `uv: command not found` failure.

## 2. Decision

1. **Standalone Linux Binary (`ed-telemetry-linux-x86_64.tar.gz`):**
   - Build a self-contained Linux executable using **PyInstaller** (`packaging/linux/ed-telemetry.spec`) embedding Python and `ed-telemetry`.
   - Never commit binaries to git; attach `ed-telemetry-linux-x86_64.tar.gz` as a **GitHub Release Asset** via GitHub Actions (`.github/workflows/release-linux.yml`) on every `v*` tag push.
2. **Self-Bootstrapping `packaging/linux/install.sh`:**
   - Probe `/api/v1/system/health`; reuse if already running.
   - Attempt to download and extract `ed-telemetry-linux-x86_64.tar.gz` from GitHub Releases into `~/.local/bin/ed-telemetry`.
   - If the release asset is unavailable, automatically bootstrap `uv` (`https://astral.sh/uv/install.sh`) and install `ed-telemetry` via `uv tool install`.
   - Run `ed-telemetry service install`.

## 3. Consequences

- **Positive:** Zero-prerequisite one-line installation on Linux (`curl -fsSL .../install.sh | bash`).
- **Negative / Trade-offs:** Requires a `ubuntu-latest` GitHub Actions runner to build and upload the Linux binary on tag releases.
