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

echo "Executing file ingestion engine and reactor tests (SDD-006 / ADR 0008)..."
wine "${PYTHON_EXE}" -c "
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, r'${WIN_REPO_ROOT}\packages')

from ed_watcher.engine import WatcherReactor, FileKind
from ed_watcher.selector import StreamPosition

with tempfile.TemporaryDirectory() as tmp_dir:
    win_dir = Path(tmp_dir)
    print(f'Temporary Windows Test Directory: {win_dir}')

    # 1. Create initial journal part 01
    j1 = win_dir / 'Journal.2026-10-09T120000.01.log'
    j1.write_bytes(b'{\"event\":\"FileHeader\",\"part\":1}\n{\"event\":\"Commander\"}\n')

    events = []
    reactor = WatcherReactor(
        journal_dir=win_dir,
        stream_position=StreamPosition.HEAD,
        data_listener=events.append,
    )
    reactor.start()
    assert reactor.is_running is True

    step1_events = reactor.step_once()
    assert len(step1_events) == 2
    assert step1_events[0].line_number == 1
    assert step1_events[1].line_number == 2
    print(f'  - Journal stream line reading on Windows ({len(step1_events)} lines): PASS')

    # 2. Test status heartbeat ingestion
    status_file = win_dir / 'Status.json'
    status_file.write_bytes(b'{\"event\":\"Status\",\"Flags\":16}')

    step2_events = reactor.step_once()
    status_events = [e for e in step2_events if e.file_kind == FileKind.STATUS]
    assert len(status_events) == 1
    assert status_events[0].raw_payload == b'{\"event\":\"Status\",\"Flags\":16}'
    print('  - Status heartbeat ingestion on Windows: PASS')

    # 3. Test part rollover transition
    j2 = win_dir / 'Journal.2026-10-09T120000.02.log'
    j2.write_bytes(b'{\"event\":\"FileHeader\",\"part\":2}\n')

    step3_events = reactor.step_once()
    rollover_events = [e for e in step3_events if e.part == 2]
    assert len(rollover_events) == 1
    assert rollover_events[0].raw_payload == b'{\"event\":\"FileHeader\",\"part\":2}\n'
    print('  - Part rollover drain-and-switch on Windows: PASS')

    reactor.stop()
    assert reactor.is_running is False

print('File ingestion engine and reactor successfully verified under Windows NT / Wine!')
"

echo "Executing FileSystemWatcher threaded adapter tests (SDD-007 / ADR 0009)..."
wine "${PYTHON_EXE}" -c "
import sys, os, tempfile, time
from pathlib import Path
sys.path.insert(0, r'${WIN_REPO_ROOT}\packages')

from ed_watcher.watcher import FileSystemWatcher
from ed_watcher.selector import StreamPosition
from ed_watcher.engine.envelopes import FileKind

with tempfile.TemporaryDirectory() as tmp_dir:
    win_dir = Path(tmp_dir)
    j1 = win_dir / 'Journal.2026-10-09T100000.01.log'
    j1.write_bytes(b'{\"event\":\"FileHeader\",\"part\":1}\n')

    events_received = []
    audits_received = []

    watcher = FileSystemWatcher(
        journal_dir=win_dir,
        stream_position=StreamPosition.HEAD,
        poll_interval=0.05,
        on_event=lambda ev: events_received.append(ev),
        on_audit=lambda aud: audits_received.append(aud),
        join_timeout=2.0,
    )

    watcher.start()
    assert watcher.is_active is True

    start_wait = time.time()
    while time.time() - start_wait < 1.5:
        if len(events_received) >= 1:
            break
        time.sleep(0.05)

    # Append new line
    with j1.open('a', encoding='utf-8') as fp:
        fp.write('{\"event\":\"Music\",\"MusicTrack\":\"MainMenu\"}\n')
        fp.flush()

    start_wait = time.time()
    while time.time() - start_wait < 1.5:
        if len(events_received) >= 2:
            break
        time.sleep(0.05)

    watcher.stop()
    assert watcher.is_active is False
    assert len(events_received) >= 2, f'Expected >= 2 events, got {len(events_received)}'
    assert any(e.file_kind == FileKind.JOURNAL for e in events_received)
    print(f'  - FileSystemWatcher background threading and dispatch on Windows ({len(events_received)} events): PASS')

print('FileSystemWatcher adapter successfully verified under Windows NT / Wine!')
"

echo "Executing Application Service Layer scaffolding tests (SDD-008 / ADR 0010)..."
wine "${PYTHON_EXE}" -c "

import sys, os
from dataclasses import FrozenInstanceError, dataclass

sys.path.insert(0, os.path.join(r'${WIN_REPO_ROOT}', 'packages'))

from ed_app.bootstrap import build_application_context
from ed_app.context import ApplicationContext
from ed_app.dto import DataTransferObject
from ed_app.exceptions import (
    ApplicationServiceError,
    ServiceDependencyError,
    ServicePayloadError,
    ServiceStateError,
)
from ed_app.services import BaseApplicationService

# 1. ApplicationContext side-effect-free instantiation
ctx = build_application_context()
assert isinstance(ctx, ApplicationContext)
assert ctx.services == ()
assert not ctx.engine.is_running
print('  - ApplicationContext instantiation and side-effect-freedom on Windows: PASS')

# 2. Immutability
try:
    ctx.services = ()  # type: ignore[misc]
    raise AssertionError('Expected FrozenInstanceError')
except FrozenInstanceError:
    pass
print('  - ApplicationContext immutability on Windows: PASS')

# 3. DTO Protocol
@dataclass(frozen=True)
class WineDTO:
    id: str
    def to_dict(self):
        return {'id': self.id}

dto = WineDTO(id='wine-test')
assert isinstance(dto, DataTransferObject)
print('  - DataTransferObject protocol compliance on Windows: PASS')

# 4. Exception hierarchy
err = ServiceDependencyError('wine test')
assert isinstance(err, ApplicationServiceError)
print('  - ApplicationServiceError hierarchy on Windows: PASS')

print('Application Service Layer scaffolding successfully verified under Windows NT / Wine!')
"

echo "============================================================"
echo "[SUCCESS] Wine Windows verification passed cleanly!"
echo "============================================================"
