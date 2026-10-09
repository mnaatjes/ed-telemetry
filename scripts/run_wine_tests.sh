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

echo "Executing journal candidate selector tests (SDD-004 / ADR 0006)..."
wine "${PYTHON_EXE}" -c "
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, r'${WIN_REPO_ROOT}\packages')

from ed_watcher.selector import JournalSelector, StreamPosition

with tempfile.TemporaryDirectory() as tmp_dir:
    win_dir = Path(tmp_dir)
    print(f'Temporary Windows Test Directory: {win_dir}')

    # 1. Test empty directory
    sel = JournalSelector(win_dir)
    assert sel.find_candidates() == (), 'Expected empty candidates'
    assert sel.get_active_journal() is None, 'Expected None for empty directory'
    print('  - Empty directory test: PASS')

    # 2. Test candidate sorting and rollover part selection
    f1 = win_dir / 'Journal.2026-10-08T120000.01.log'
    f2 = win_dir / 'Journal.2026-10-08T120000.02.log'
    f_legacy = win_dir / 'Journal.220101120000.01.log'
    f_status = win_dir / 'Status.json'

    for f in (f1, f2, f_legacy, f_status):
        f.touch()

    candidates = sel.find_candidates()
    assert len(candidates) == 3, f'Expected 3 candidates, found {len(candidates)}'
    print(f'  - Candidate filtering test ({len(candidates)} found): PASS')

    active = sel.get_active_journal()
    assert active is not None, 'Active journal should not be None'
    assert active.filename == 'Journal.2026-10-08T120000.02.log', f'Wrong active journal: {active.filename}'
    print(f'  - Active journal selection test ({active.filename}): PASS')

    # 3. Test runtime successor detection
    c1 = [c for c in candidates if c.part == 1 and c.timestamp.year == 2026][0]
    successor = sel.get_successor(c1)
    assert successor is not None, 'Expected successor for part 01'
    assert successor.part == 2, f'Expected part 2, got {successor.part}'
    print(f'  - Successor detection test (part 01 -> part 02): PASS')

print('Journal candidate selection successfully verified under Windows NT / Wine!')
"

echo "Executing status and snapshot identifier tests (SDD-005 / ADR 0007)..."
wine "${PYTHON_EXE}" -c "
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, r'${WIN_REPO_ROOT}\packages')

from ed_watcher.snapshots import SnapshotIdentifier, SnapshotRegistry

with tempfile.TemporaryDirectory() as tmp_dir:
    win_dir = Path(tmp_dir)
    print(f'Temporary Windows Test Directory: {win_dir}')

    ident = SnapshotIdentifier(win_dir)

    # 1. Test empty directory returns None
    assert ident.resolve_status() is None
    assert ident.resolve_auxiliary('Market.json') is None
    print('  - Empty snapshot resolution test: PASS')

    # 2. Test status and auxiliary snapshot discovery
    (win_dir / 'Status.json').write_text('{\"event\": \"Status\"}')
    (win_dir / 'Market.json').write_text('{\"event\": \"Market\"}')
    (win_dir / 'Cargo.json').write_text('{\"event\": \"Cargo\"}')

    status_cand = ident.resolve_status()
    assert status_cand is not None
    assert status_cand.canonical_name == 'Status.json'
    assert status_cand.size > 0
    print(f'  - Status snapshot resolution ({status_cand.canonical_name}): PASS')

    market_cand = ident.resolve_auxiliary('Market.json')
    assert market_cand is not None
    assert market_cand.canonical_name == 'Market.json'
    print(f'  - Auxiliary snapshot resolution ({market_cand.canonical_name}): PASS')

    all_cands = ident.resolve_all_available()
    assert len(all_cands) == 3
    print(f'  - All available snapshots resolution ({len(all_cands)} found): PASS')

print('Status and snapshot identifier successfully verified under Windows NT / Wine!')
"

echo "============================================================"
echo "[SUCCESS] Wine Windows verification passed cleanly!"
echo "============================================================"
