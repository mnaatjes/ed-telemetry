#!/usr/bin/env bash
# ==============================================================================
# scripts/setup_wine_simulant.sh
#
# Idempotently initializes an isolated Wine prefix and downloads an embeddable
# Windows Python runtime for local cross-platform verification on Linux.
# Governed by SDD-003 and ADR 0005.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${REPO_ROOT}/.cache"
WINE_PREFIX="${CACHE_DIR}/winepfx"
DOWNLOADS_DIR="${CACHE_DIR}/downloads"
PYTHON_TARGET_DIR="${WINE_PREFIX}/drive_c/Python311"
PYTHON_VERSION="3.11.9"
PYTHON_ZIP="python-${PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_ZIP}"

echo "============================================================"
echo "Initializing Isolated Wine Environment for Windows Testing"
echo "============================================================"

# 1. Pre-flight host binary checks
if ! command -v wine >/dev/null 2>&1; then
    echo "[ERROR] 'wine' is not installed on this host."
    echo "To install on Debian/Ubuntu, run:"
    echo "    sudo apt-get update && sudo apt-get install -y wine64 wine-binfmt"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "[ERROR] 'curl' is required but not installed."
    exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
    echo "[ERROR] 'unzip' is required but not installed."
    exit 1
fi

# 2. Fast-exit if already provisioned
if [[ -f "${PYTHON_TARGET_DIR}/python.exe" ]]; then
    echo "[INFO] Windows Python is already installed at: ${PYTHON_TARGET_DIR}/python.exe"
    echo "[SUCCESS] Wine simulant environment is ready."
    exit 0
fi

# 3. Initialize isolated Wine prefix
mkdir -p "${DOWNLOADS_DIR}" "${PYTHON_TARGET_DIR}"
export WINEPREFIX="${WINE_PREFIX}"
export WINEDLLOVERRIDES="mscoree,mshtml=" # Suppress Gecko/Mono dialog prompts
export WINEDEBUG="-all"                  # Suppress Wine debug noise

echo "[1/3] Initializing isolated Wine prefix at: ${WINE_PREFIX}..."
wineboot --init >/dev/null 2>&1 || true

# 4. Download embeddable Windows Python
if [[ ! -f "${DOWNLOADS_DIR}/${PYTHON_ZIP}" ]]; then
    echo "[2/3] Downloading Windows Python ${PYTHON_VERSION} embeddable package..."
    curl -fsSL "${PYTHON_URL}" -o "${DOWNLOADS_DIR}/${PYTHON_ZIP}"
else
    echo "[2/3] Found cached package: ${DOWNLOADS_DIR}/${PYTHON_ZIP}"
fi

# 5. Extract into Wine drive_c
echo "[3/3] Extracting Python into: ${PYTHON_TARGET_DIR}..."
unzip -qo "${DOWNLOADS_DIR}/${PYTHON_ZIP}" -d "${PYTHON_TARGET_DIR}"

# Enable site-packages in embeddable python by updating ._pth file
PTH_FILE="${PYTHON_TARGET_DIR}/python311._pth"
if [[ -f "${PTH_FILE}" ]]; then
    # Uncomment 'import site' in the ._pth file to enable standard site packages
    sed -i 's/#import site/import site/' "${PTH_FILE}"
fi

echo "============================================================"
echo "[SUCCESS] Wine simulant environment provisioned successfully!"
echo "Target: ${PYTHON_TARGET_DIR}/python.exe"
echo "Run tests using: ./scripts/run_wine_tests.sh"
echo "============================================================"
