"""Unit tests for diagnostic logging buffer and cross-platform path resolution."""

import logging
from pathlib import Path
from unittest.mock import patch

from ed_telemetry.adapters.driven.logging.buffer import DiagnosticLogBuffer
from ed_telemetry.bootstrap.container import resolve_default_log_path
from ed_telemetry.core.ports.dto.telemetry_dto import DiagnosticLogSnapshotDTO
from ed_telemetry.core.use_cases.get_diagnostic_logs import GetDiagnosticLogsUseCase
from tests.doubles.fake_adapters import FakeDiagnosticLogAdapter


def test_diagnostic_log_buffer_records_and_filters():
    buffer = DiagnosticLogBuffer(capacity=10)
    logger = logging.getLogger("test_diagnostics")
    logger.addHandler(buffer)
    logger.setLevel(logging.DEBUG)

    try:
        logger.debug("Debug entry")
        logger.info("Info entry")
        logger.warning("Warning entry")
        logger.error("Error entry")

        # Query all
        snap_all = buffer.get_recent_logs()
        assert snap_all.total_retained == 4
        assert snap_all.records[0].level == "DEBUG"
        assert snap_all.records[3].level == "ERROR"

        # Query min_level WARNING
        snap_warn = buffer.get_recent_logs(min_level="WARNING")
        assert snap_warn.total_retained == 2
        assert [r.level for r in snap_warn.records] == ["WARNING", "ERROR"]

        # Query with limit
        snap_lim = buffer.get_recent_logs(limit=2)
        assert snap_lim.total_retained == 2
        assert [r.level for r in snap_lim.records] == ["WARNING", "ERROR"]

        # Buffer capacity eviction
        for i in range(15):
            logger.info("Flood %d", i)
        snap_capped = buffer.get_recent_logs(limit=100)
        assert snap_capped.total_retained == 10
        assert snap_capped.records[-1].message == "Flood 14"
    finally:
        logger.removeHandler(buffer)


def test_get_diagnostic_logs_use_case():
    fake_adapter = FakeDiagnosticLogAdapter()
    use_case = GetDiagnosticLogsUseCase(log_port=fake_adapter)

    res = use_case.get_logs(min_level="INFO", limit=50)
    assert isinstance(res, DiagnosticLogSnapshotDTO)
    assert res.total_retained == 0


def test_resolve_default_log_path_windows():
    with patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\Pilot\\AppData\\Local"}):
        path = resolve_default_log_path(platform="win32")
        assert path.name == "ed-telemetry.log"
        assert path.parts[-3:] == ("ed-telemetry", "logs", "ed-telemetry.log")


def test_resolve_default_log_path_linux():
    with patch.dict("os.environ", {"XDG_STATE_HOME": "/home/deck/.local/state"}):
        path = resolve_default_log_path(platform="linux")
        assert path == Path("/home/deck/.local/state/ed-telemetry/ed-telemetry.log")
