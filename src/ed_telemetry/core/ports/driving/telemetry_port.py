"""Driving (inbound / primary) port contracts."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from ..base import DrivingPort
from ..dto.telemetry_dto import (
    AuxiliarySnapshotDTO,
    DatabaseMaintenanceResultDTO,
    DatabaseStatsDTO,
    DiagnosticLogRecordDTO,
    DiagnosticLogSnapshotDTO,
    GameStatusSnapshotDTO,
    HintSubmissionDTO,
    JournalFileListDTO,
    JournalPathDTO,
    SnapshotSyncResultDTO,
    StartMonitoringDTO,
    TelemetryBatchDTO,
    TelemetryPayloadDTO,
    TelemetryQueryDTO,
    TelemetryRecordDTO,
    WatcherStatusDTO,
)


@runtime_checkable
class GetWatcherStatusPort(DrivingPort, Protocol):
    """Primary driving port for querying telemetry watcher operational health and status."""

    def get_status(self) -> WatcherStatusDTO: ...


@runtime_checkable
class ProcessTelemetryStreamPort(DrivingPort, Protocol):
    """Primary driving port for managing continuous inbound telemetry event ingestion."""

    def start_streaming(self, command: StartMonitoringDTO | None = None) -> None: ...

    def stop_streaming(self) -> None: ...


@runtime_checkable
class SyncJournalSnapshotPort(DrivingPort, Protocol):
    """Primary driving port for executing point-in-time synchronization of journal and status snapshots."""

    def sync_snapshots(self) -> SnapshotSyncResultDTO: ...


@runtime_checkable
class FindJournalPathPort(DrivingPort, Protocol):
    """Primary driving port for discovering the Elite Dangerous journal directory."""

    def find_path(self, override_path: str | None = None) -> JournalPathDTO: ...


@runtime_checkable
class GetJournalFilesPort(DrivingPort, Protocol):
    """Primary driving port for listing candidate journal files in chronological order."""

    def get_journals(self) -> JournalFileListDTO: ...


@runtime_checkable
class GetLatestGameStatusPort(DrivingPort, Protocol):
    """Primary driving port for inspecting current Status.json state."""

    def get_game_status(self) -> GameStatusSnapshotDTO: ...


@runtime_checkable
class GetAuxiliarySnapshotPort(DrivingPort, Protocol):
    """Primary driving port for inspecting an auxiliary state snapshot."""

    def get_snapshot(self, snapshot_name: str) -> AuxiliarySnapshotDTO: ...


@runtime_checkable
class SubmitSnapshotRefreshPort(DrivingPort, Protocol):
    """Primary driving port for submitting an immediate snapshot re-read hint."""

    def refresh_snapshot(self, snapshot_name: str) -> HintSubmissionDTO: ...


@runtime_checkable
class GetTelemetryEventsPort(DrivingPort, Protocol):
    """Primary driving port for polling buffered telemetry event payloads."""

    def get_events(self, limit: int = 100, timeout: float | None = None) -> TelemetryBatchDTO: ...


@runtime_checkable
class FindTelemetryEventsPort(DrivingPort, Protocol):
    """Primary driving port for querying historical telemetry events from persistence."""

    def find_events(self, query: TelemetryQueryDTO) -> tuple[TelemetryRecordDTO, ...]: ...


@runtime_checkable
class GetTelemetryStreamPort(DrivingPort, Protocol):
    """Primary driving port for streaming live telemetry events."""

    def stream_events(self, timeout: float | None = 1.0) -> Iterator[TelemetryPayloadDTO]: ...


@runtime_checkable
class GetDiagnosticLogsPort(DrivingPort, Protocol):
    """Primary driving port for retrieving diagnostic log snapshots."""

    def get_logs(
        self,
        min_level: str | None = None,
        limit: int = 100,
    ) -> DiagnosticLogSnapshotDTO: ...


@runtime_checkable
class GetDatabaseStatsPort(DrivingPort, Protocol):
    """Primary driving port for inspecting SQLite database metrics and storage."""

    def get_stats(self) -> DatabaseStatsDTO: ...


@runtime_checkable
class MaintainDatabasePort(DrivingPort, Protocol):
    """Primary driving port for pruning and maintaining the SQLite database."""

    def maintain(
        self,
        retention_days: int | None = None,
        max_records: int | None = None,
        run_vacuum: bool = False,
    ) -> DatabaseMaintenanceResultDTO: ...


__all__ = (
    "FindJournalPathPort",
    "FindTelemetryEventsPort",
    "GetAuxiliarySnapshotPort",
    "GetDatabaseStatsPort",
    "GetDiagnosticLogsPort",
    "GetJournalFilesPort",
    "GetLatestGameStatusPort",
    "GetTelemetryEventsPort",
    "GetTelemetryStreamPort",
    "GetWatcherStatusPort",
    "MaintainDatabasePort",
    "ProcessTelemetryStreamPort",
    "SubmitSnapshotRefreshPort",
    "SyncJournalSnapshotPort",
    "AuxiliarySnapshotDTO",
    "DatabaseMaintenanceResultDTO",
    "DatabaseStatsDTO",
    "DiagnosticLogRecordDTO",
    "DiagnosticLogSnapshotDTO",
    "GameStatusSnapshotDTO",
    "HintSubmissionDTO",
    "JournalFileListDTO",
    "JournalPathDTO",
    "SnapshotSyncResultDTO",
    "StartMonitoringDTO",
    "TelemetryBatchDTO",
    "TelemetryPayloadDTO",
    "TelemetryQueryDTO",
    "TelemetryRecordDTO",
    "WatcherStatusDTO",
)
