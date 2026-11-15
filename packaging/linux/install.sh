#!/usr/bin/env bash
set -euo pipefail

# Idempotent 4-step installer for ed-telemetry on Linux (SteamOS / Desktop)
HEALTH_URL="${ED_TELEMETRY_URL:-http://127.0.0.1:8080}/api/v1/system/health"

# 1. Probe
if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "ed-telemetry is already running at $HEALTH_URL. Reusing existing instance."
  exit 0
fi

# 2. Install
uv tool install --upgrade ed-telemetry

# 3. Register & 4. Start
ed-telemetry service install
echo "ed-telemetry installed and started."
