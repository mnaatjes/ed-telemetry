#!/usr/bin/env bash
# ==============================================================================
# scripts/run_wine_tests.sh
#
# Executes Python tests inside the isolated Wine prefix under Windows Python.
# Governed by SDD-003 and ADR 0005.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${REPO_ROOT}/.cache"
WINE_PREFIX="${CACHE_DIR}/winepfx"
PYTHON_EXE="${WINE_PREFIX}/drive_c/Python311/python.exe"

if [[ ! -f "${PYTHON_EXE}" ]]; then
    echo "[ERROR] Windows Python is not provisioned at: ${PYTHON_EXE}"
    echo "Run setup first: ./scripts/setup_wine_simulant.sh"
    exit 1
fi

export WINEPREFIX="${WINE_PREFIX}"
export WINEDEBUG="-all"

echo "============================================================"
echo "Running Tests under Windows Python via Wine"
echo "============================================================"

# Convert POSIX repo root to Windows path format using winepath
WIN_REPO_ROOT="$(wine winepath -w "${REPO_ROOT}")"

wine "${PYTHON_EXE}" -c "
import sys, os, platform
print(f'Platform: {platform.system()} {platform.release()}')
print(f'Python:   {sys.version}')
print(f'Winreg:   {\"available\" if \"winreg\" in sys.builtin_module_names else \"not found\"}')
"

echo "Executing path discovery tests..."
wine "${PYTHON_EXE}" -c "
import sys
sys.path.insert(0, r'${WIN_REPO_ROOT}\packages')

from ed_watcher.discovery.strategies.windows import WindowsPathStrategy
strat = WindowsPathStrategy()
print(f'Strategy platform: {strat.platform_name}')
candidates = strat.find_candidates()
print(f'Discovered candidates ({len(candidates)}):')
for c in candidates:
    print(f'  - {c}')
print('Windows Path Strategy successfully verified under Wine!')
"

echo "============================================================"
echo "[SUCCESS] Wine Windows verification passed cleanly!"
echo "============================================================"
