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

# 5. Post-install health check & summary
HEALTH_JSON=""
for _ in $(seq 1 10); do
  if HEALTH_JSON="$(curl -fsS "$HEALTH_URL" 2>/dev/null)"; then
    break
  fi
  sleep 0.5
done

if [[ -z "$HEALTH_JSON" ]]; then
  echo "ERROR: ed-telemetry failed to respond at $HEALTH_URL" >&2
  echo "Check logs: journalctl --user -u ed-telemetry.service -n 20 --no-pager" >&2
  exit 1
fi

LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
echo ""
echo "ed-telemetry installed and running!"
echo "  Health:   $HEALTH_JSON"
echo "  Local:    http://127.0.0.1:8080"
if [[ -n "$LAN_IP" ]]; then
  echo "  LAN:      http://${LAN_IP}:8080"
fi
echo "  Security: --allow-insecure (no API key required)"
echo "  Status:   systemctl --user status ed-telemetry.service"
echo "  Logs:     journalctl --user -u ed-telemetry.service -f"
