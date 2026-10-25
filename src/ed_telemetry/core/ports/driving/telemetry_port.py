"""Driving (inbound / primary) port contracts and boundary DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..base import DataTransferObject, DrivingPort


@dataclass(frozen=True, slots=True)
class WatcherStatusDTO(DataTransferObject):
    """Immutable status snapshot of the telemetry watcher system."""

    is_active: bool
    active_journal: str | None
    monitored_directory: str | None


@dataclass(frozen=True, slots=True)
class StartMonitoringCommand(DataTransferObject):
    """Command payload instructing use case to start telemetry monitoring."""

    journal_dir: Path | None = None
    poll_interval: float | None = None


@dataclass(frozen=True, slots=True)
class SnapshotSyncResultDTO(DataTransferObject):
    """Summary of point-in-time snapshot synchronization."""

    files_inspected: int
    payloads_emitted: int
    active_journal_file: str | None


@runtime_checkable
class GetWatcherStatusPort(DrivingPort, Protocol):
    """Primary driving port for querying telemetry watcher operational health and status."""

    def get_status(self) -> WatcherStatusDTO: ...


@runtime_checkable
class ProcessTelemetryStreamPort(DrivingPort, Protocol):
    """Primary driving port for managing continuous inbound telemetry event ingestion."""

    def start_streaming(self, command: StartMonitoringCommand | None = None) -> None: ...

    def stop_streaming(self) -> None: ...


@runtime_checkable
class SyncJournalSnapshotPort(DrivingPort, Protocol):
    """Primary driving port for executing point-in-time synchronization of journal and status snapshots."""

    def sync_snapshots(self) -> SnapshotSyncResultDTO: ...
