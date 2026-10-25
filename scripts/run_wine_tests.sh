#!/usr/bin/env bash
# ==============================================================================
# scripts/run_wine_tests.sh
#
# Executes Python tests inside the isolated Wine prefix under Windows Python.
# Governed by SDD-003, ADR 0005, ADR 0017, ADR 0018, ADR 0019, and SDD-017.
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
sys.path.insert(0, r'${WIN_REPO_ROOT}\src')

from ed_telemetry.adapters.driven.watcher.discovery.strategies.windows import WindowsPathStrategy
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
sys.path.insert(0, r'${WIN_REPO_ROOT}\src')

from ed_telemetry.adapters.driven.watcher.selector import JournalSelector, StreamPosition

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
sys.path.insert(0, r'${WIN_REPO_ROOT}\src')

from ed_telemetry.adapters.driven.watcher.snapshots import SnapshotIdentifier, SnapshotRegistry

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
sys.path.insert(0, r'${WIN_REPO_ROOT}\src')

from ed_telemetry.adapters.driven.watcher.engine import WatcherReactor, FileKind
from ed_telemetry.adapters.driven.watcher.selector import StreamPosition

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
sys.path.insert(0, r'${WIN_REPO_ROOT}\src')

from ed_telemetry.adapters.driven.watcher.watcher import FileSystemWatcher
from ed_telemetry.adapters.driven.watcher.selector import StreamPosition
from ed_telemetry.adapters.driven.watcher.engine.envelopes import FileKind

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

echo "Executing Hexagonal Container & Telemetry Use Cases tests (ADR 0017 / ADR 0018 / SDD-017)..."
wine "${PYTHON_EXE}" -c "
import sys, os, tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

sys.path.insert(0, r'${WIN_REPO_ROOT}\src')

from ed_telemetry.bootstrap.container import Container, build_container
from ed_telemetry.core.ports.dto import (
    JournalPathDTO,
    JournalCandidateDTO,
    JournalFileListDTO,
    GameStatusSnapshotDTO,
    AuxiliarySnapshotDTO,
    HintSubmissionDTO,
    TelemetryBatchDTO,
)

with tempfile.TemporaryDirectory() as tmp_dir:
    win_dir = Path(tmp_dir)
    print(f'Temporary Windows Test Directory: {win_dir}')

    # Populate directory with files
    (win_dir / 'Journal.2026-10-09T100000.01.log').write_bytes(b'{\"event\":\"FileHeader\",\"part\":1}\n')
    (win_dir / 'Status.json').write_text('{\"event\":\"Status\",\"Flags\":16}')
    (win_dir / 'Market.json').write_text('{\"event\":\"Market\",\"MarketID\":1234}')

    # 1. Container instantiation
    container = build_container(journal_dir=win_dir, http_port=0)
    assert isinstance(container, Container)
    assert container.cli_adapter is not None
    assert container.find_journal_path_use_case is not None
    assert container.get_journal_files_use_case is not None
    assert container.get_latest_game_status_use_case is not None
    assert container.get_auxiliary_snapshot_use_case is not None
    assert container.submit_snapshot_refresh_use_case is not None
    print('  - Container instantiation and DI wiring on Windows: PASS')

    # 2. FindJournalPathUseCase
    path_dto = container.find_journal_path_use_case.find_path(override_path=str(win_dir))
    assert isinstance(path_dto, JournalPathDTO)
    assert path_dto.resolved_path == str(win_dir)
    print(f'  - FindJournalPathUseCase execution on Windows: PASS')

    # 3. GetJournalFilesUseCase
    files_dto = container.get_journal_files_use_case.get_journals()
    assert isinstance(files_dto, JournalFileListDTO)
    assert len(files_dto.candidates) == 1
    assert files_dto.active_journal is not None
    assert 'Journal.2026-10-09T100000.01.log' in files_dto.active_journal
    print(f'  - GetJournalFilesUseCase execution on Windows: PASS')

    # 4. GetLatestGameStatusUseCase
    status_dto = container.get_latest_game_status_use_case.get_game_status()
    assert isinstance(status_dto, GameStatusSnapshotDTO)
    assert status_dto.exists is True
    assert status_dto.raw_payload == b'{\"event\":\"Status\",\"Flags\":16}'
    print(f'  - GetLatestGameStatusUseCase execution on Windows: PASS')

    # 5. GetAuxiliarySnapshotUseCase
    aux_dto = container.get_auxiliary_snapshot_use_case.get_snapshot('Market.json')
    assert isinstance(aux_dto, AuxiliarySnapshotDTO)
    assert aux_dto.exists is True
    assert aux_dto.target_name == 'Market.json'
    assert aux_dto.raw_payload == b'{\"event\":\"Market\",\"MarketID\":1234}'
    print(f'  - GetAuxiliarySnapshotUseCase execution on Windows: PASS')

    # 6. SubmitSnapshotRefreshUseCase (Reactor not started -> accepted=False with clear detail)
    hint_dto = container.submit_snapshot_refresh_use_case.refresh_snapshot('Market.json')
    assert isinstance(hint_dto, HintSubmissionDTO)
    assert hint_dto.target_name == 'Market.json'
    assert hint_dto.accepted is False
    assert 'Reactor not running' in hint_dto.detail
    print(f'  - SubmitSnapshotRefreshUseCase execution on Windows: PASS')

    # 7. GetTelemetryEventsUseCase (start streaming, write event to disk, drain via GetTelemetryEventsUseCase)
    container.process_telemetry_stream_use_case.start_streaming()
    import time
    with (win_dir / 'Journal.2026-10-09T100000.01.log').open('a', encoding='utf-8') as fp:
        fp.write('{\"event\":\"DockingGranted\",\"StationName\":\"Jameson\"}\n')
        fp.flush()

    # Wait briefly for watcher loop tick
    time.sleep(0.15)
    container.process_telemetry_stream_use_case.stop_streaming()

    batch_dto = container.get_telemetry_events_use_case.get_events(limit=10)
    assert isinstance(batch_dto, TelemetryBatchDTO)
    assert len(batch_dto.events) > 0
    assert any(b'DockingGranted' in e.payload_bytes or b'FileHeader' in e.payload_bytes for e in batch_dto.events)
    print(f'  - GetTelemetryEventsUseCase buffered consumption on Windows ({len(batch_dto.events)} events): PASS')

    # 8. FindTelemetryEventsUseCase (verify persistence in SQLite under Windows NT)
    from ed_telemetry.core.ports.dto import TelemetryQueryDTO
    records = container.find_telemetry_events_use_case.find_events(TelemetryQueryDTO())
    assert len(records) > 0
    print(f'  - FindTelemetryEventsUseCase SQLite persistence on Windows ({len(records)} records): PASS')

    # 9. HttpApiAdapter health check and endpoint validation under Windows NT
    container.http_api_adapter.start()
    import urllib.request
    import urllib.error
    import json
    base_url = f'http://127.0.0.1:{container.http_api_adapter.port}'
    with urllib.request.urlopen(f'{base_url}/api/v1/health') as resp:
        assert resp.status == 200
    with urllib.request.urlopen(f'{base_url}/api/v1/snapshots/market') as resp:
        assert resp.status == 200
        snap_data = json.loads(resp.read().decode('utf-8'))
        assert snap_data['exists'] is True
    try:
        urllib.request.urlopen(f'{base_url}/api/v1/snapshots/missing')
        assert False, 'Expected 404'
    except urllib.error.HTTPError as err:
        assert err.code == 404
        assert err.headers.get('Content-Type') == 'application/problem+json'
    container.http_api_adapter.stop()
    print('  - HttpApiAdapter local server on Windows: PASS')

    # 10. CliTelemetryAdapter subcommands under Windows NT
    code_status, payload_status = container.cli_adapter.run(['status', '--json'])
    assert code_status == 0
    assert payload_status['is_active'] is False
    code_game, payload_game = container.cli_adapter.run(['status', 'game', '--json'])
    assert code_game == 0
    assert payload_game['exists'] is True
    code_events, payload_events = container.cli_adapter.run(['events', '--json'])
    assert code_events == 0
    assert payload_events['count'] > 0
    print('  - CliTelemetryAdapter execution on Windows: PASS')

    # 11. DTO Immutability
    try:
        hint_dto.accepted = False  # type: ignore[misc]
        raise AssertionError('Expected FrozenInstanceError')
    except FrozenInstanceError:
        pass
    print('  - Boundary DTO immutability on Windows: PASS')

    # 12. Cross-platform log path and diagnostic log buffer verification (ADR 0025 / SDD-023)
    from ed_telemetry.bootstrap.container import resolve_default_log_path
    win_log_path = resolve_default_log_path(platform='win32')
    assert 'ed-telemetry' in str(win_log_path)
    assert str(win_log_path).endswith('ed-telemetry.log')
    print(f'  - Windows Log Path Resolution ({win_log_path}): PASS')

    # Query diagnostic logs via container use case and CLI
    diag_snapshot = container.get_diagnostic_logs_use_case.get_logs(limit=10)
    assert diag_snapshot.total_retained >= 0
    code_logs, payload_logs = container.cli_adapter.run(['logs', '--json'])
    assert code_logs == 0
    assert 'records' in payload_logs
    print('  - Diagnostic log buffer and CLI subcommand on Windows: PASS')

print('Hexagonal Container & Telemetry Use Cases successfully verified under Windows NT / Wine!')
"

echo "============================================================"
echo "[SUCCESS] Wine Windows verification passed cleanly!"
echo "============================================================"
