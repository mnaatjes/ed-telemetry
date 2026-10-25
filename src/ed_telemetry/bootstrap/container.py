"""Composition root wiring adapters and interactors into executable runtime services."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..adapters.driven.egress.buffered_queue import BufferedQueueAdapter
from ..adapters.driven.egress.composite import CompositeEgressAdapter
from ..adapters.driven.logging.buffer import DiagnosticLogBuffer
from ..adapters.driven.persistence.sqlite_adapter import (
    SqliteEgressAdapter,
    SqlitePersistenceManager,
    SqliteRepositoryAdapter,
)
from ..adapters.driven.watcher.watcher import FileSystemWatcher
from ..adapters.driving.api.server import HttpApiAdapter
from ..adapters.driving.cli.main import CliTelemetryAdapter
from ..core.use_cases.find_journal_path import FindJournalPathUseCase
from ..core.use_cases.find_telemetry_events import FindTelemetryEventsUseCase
from ..core.use_cases.get_auxiliary_snapshot import GetAuxiliarySnapshotUseCase
from ..core.use_cases.get_diagnostic_logs import GetDiagnosticLogsUseCase
from ..core.use_cases.get_journal_files import GetJournalFilesUseCase
from ..core.use_cases.get_latest_game_status import GetLatestGameStatusUseCase
from ..core.use_cases.get_telemetry_events import GetTelemetryEventsUseCase
from ..core.use_cases.get_telemetry_stream import GetTelemetryStreamUseCase
from ..core.use_cases.get_watcher_status import GetWatcherStatusUseCase
from ..core.use_cases.process_telemetry_stream import ProcessTelemetryStreamUseCase
from ..core.use_cases.submit_snapshot_refresh import SubmitSnapshotRefreshUseCase
from ..core.use_cases.sync_journal_snapshot import SyncJournalSnapshotUseCase


def resolve_default_log_path(platform: str | None = None) -> Path:
    """Resolve cross-platform rotating log path according to OS standards."""
    current_platform = platform or sys.platform

    if current_platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ed-telemetry" / "logs" / "ed-telemetry.log"
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            return Path(user_profile) / ".cache" / "ed-telemetry" / "logs" / "ed-telemetry.log"
        return Path.home() / ".cache" / "ed-telemetry" / "logs" / "ed-telemetry.log"

    # Linux / SteamDeck / Unix
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "ed-telemetry" / "ed-telemetry.log"

    state_home = Path.home() / ".local" / "state" / "ed-telemetry" / "ed-telemetry.log"
    return state_home


@dataclass(frozen=True, slots=True)
class Container:
    """Dependency injection container graph holding singleton use cases and driving adapters."""

    get_watcher_status_use_case: GetWatcherStatusUseCase
    process_telemetry_stream_use_case: ProcessTelemetryStreamUseCase
    sync_journal_snapshot_use_case: SyncJournalSnapshotUseCase
    find_journal_path_use_case: FindJournalPathUseCase
    get_journal_files_use_case: GetJournalFilesUseCase
    get_latest_game_status_use_case: GetLatestGameStatusUseCase
    get_auxiliary_snapshot_use_case: GetAuxiliarySnapshotUseCase
    submit_snapshot_refresh_use_case: SubmitSnapshotRefreshUseCase
    get_telemetry_events_use_case: GetTelemetryEventsUseCase
    find_telemetry_events_use_case: FindTelemetryEventsUseCase
    get_telemetry_stream_use_case: GetTelemetryStreamUseCase
    get_diagnostic_logs_use_case: GetDiagnosticLogsUseCase
    diagnostic_log_buffer: DiagnosticLogBuffer
    cli_adapter: CliTelemetryAdapter
    http_api_adapter: HttpApiAdapter


def build_container(
    journal_dir: Path | None = None,
    poll_interval: float | None = None,
    buffer_capacity: int = 10000,
    db_path: Path | str | None = None,
    http_host: str = "127.0.0.1",
    http_port: int = 8080,
    log_level: str = "INFO",
    log_file: Path | str | None = None,
    diagnostic_buffer_capacity: int = 1000,
) -> Container:
    """Instantiate concrete driven adapters, wire use cases, and instantiate driving adapters."""
    # Configure logging and ring buffer
    diagnostic_buffer = DiagnosticLogBuffer(capacity=diagnostic_buffer_capacity)
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Attach ring buffer if not already attached
    if not any(isinstance(h, DiagnosticLogBuffer) for h in root_logger.handlers):
        root_logger.addHandler(diagnostic_buffer)

    # Attach rotating file handler
    effective_log_path = Path(log_file) if log_file else resolve_default_log_path()
    try:
        effective_log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(effective_log_path),
            maxBytes=5_242_880,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
            root_logger.addHandler(file_handler)
    except OSError as err:
        logging.warning("Unable to initialize rotating file logger at %s: %s", effective_log_path, err)

    watcher = FileSystemWatcher(journal_dir=journal_dir, poll_interval=poll_interval)
    egress_buffer = BufferedQueueAdapter(maxsize=buffer_capacity)

    effective_db = Path(db_path) if db_path else Path(".cache/telemetry.db")
    db_manager = SqlitePersistenceManager(db_path=effective_db)
    sqlite_egress = SqliteEgressAdapter(manager=db_manager)
    sqlite_repo = SqliteRepositoryAdapter(manager=db_manager)

    composite_egress = CompositeEgressAdapter(sinks=[egress_buffer, sqlite_egress])

    get_status = GetWatcherStatusUseCase(watcher=watcher)
    process_stream = ProcessTelemetryStreamUseCase(watcher=watcher, egress=composite_egress)
    sync_snapshot = SyncJournalSnapshotUseCase(watcher=watcher, egress=composite_egress)
    find_path = FindJournalPathUseCase(watcher=watcher)
    get_journals = GetJournalFilesUseCase(watcher=watcher)
    get_game_status = GetLatestGameStatusUseCase(watcher=watcher)
    get_aux = GetAuxiliarySnapshotUseCase(watcher=watcher)
    submit_refresh = SubmitSnapshotRefreshUseCase(watcher=watcher)
    get_events = GetTelemetryEventsUseCase(queue=egress_buffer)
    find_events = FindTelemetryEventsUseCase(repository=sqlite_repo)
    stream_events = GetTelemetryStreamUseCase(queue=egress_buffer)
    get_diagnostic_logs = GetDiagnosticLogsUseCase(log_port=diagnostic_buffer)

    http_api_adapter = HttpApiAdapter(
        host=http_host,
        port=http_port,
        watcher_status_port=get_status,
        process_stream_port=process_stream,
        find_events_port=find_events,
        get_events_port=get_events,
        stream_events_port=stream_events,
        game_status_port=get_game_status,
        journal_path_port=find_path,
        journal_files_port=get_journals,
        aux_snapshot_port=get_aux,
        diagnostic_logs_port=get_diagnostic_logs,
    )
    cli_adapter = CliTelemetryAdapter(
        watcher_status_port=get_status,
        game_status_port=get_game_status,
        find_events_port=find_events,
        process_stream_port=process_stream,
        http_api_adapter=http_api_adapter,
        diagnostic_logs_port=get_diagnostic_logs,
        stream_events_port=stream_events,
    )

    return Container(
        get_watcher_status_use_case=get_status,
        process_telemetry_stream_use_case=process_stream,
        sync_journal_snapshot_use_case=sync_snapshot,
        find_journal_path_use_case=find_path,
        get_journal_files_use_case=get_journals,
        get_latest_game_status_use_case=get_game_status,
        get_auxiliary_snapshot_use_case=get_aux,
        submit_snapshot_refresh_use_case=submit_refresh,
        get_telemetry_events_use_case=get_events,
        find_telemetry_events_use_case=find_events,
        get_telemetry_stream_use_case=stream_events,
        get_diagnostic_logs_use_case=get_diagnostic_logs,
        diagnostic_log_buffer=diagnostic_buffer,
        cli_adapter=cli_adapter,
        http_api_adapter=http_api_adapter,
    )


def main() -> int:
    """CLI execution entrypoint wired from composition root."""
    container = build_container()
    code, _ = container.cli_adapter.run()
    return code
