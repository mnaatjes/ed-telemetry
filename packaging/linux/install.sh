#!/usr/bin/env bash
set -euo pipefail

# Idempotent 4-step installer for ed-telemetry on Linux (SteamOS / Desktop)
HEALTH_URL="${ED_TELEMETRY_URL:-http://127.0.0.1:8080}/api/v1/system/health"
RELEASE_URL="https://github.com/mnaatjes/ed-telemetry/releases/latest/download/ed-telemetry-linux-x86_64.tar.gz"
BIN_DIR="${HOME}/.local/bin"

# 1. Probe
if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "ed-telemetry is already running at $HEALTH_URL. Reusing existing instance."
  exit 0
fi

# 2. Install (prefer standalone release tarball; fallback to uv tool install)
mkdir -p "$BIN_DIR"
export PATH="${BIN_DIR}:${PATH}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if curl -fsSL "$RELEASE_URL" -o "${TMP_DIR}/ed-telemetry.tar.gz" 2>/dev/null; then
  rm -f "${BIN_DIR}/ed-telemetry"
  tar -xzf "${TMP_DIR}/ed-telemetry.tar.gz" -C "$BIN_DIR"
  chmod +x "${BIN_DIR}/ed-telemetry"
else
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
  uv tool install --upgrade --force git+https://github.com/mnaatjes/ed-telemetry.git
fi

# 3. Register & 4. Start
ed-telemetry service install
echo "ed-telemetry installed and started."
