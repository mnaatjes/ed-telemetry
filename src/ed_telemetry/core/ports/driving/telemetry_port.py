"""Driving (inbound / primary) port contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..base import DrivingPort
from ..dto.telemetry_dto import (
    SnapshotSyncResultDTO,
    StartMonitoringDTO,
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


__all__ = (
    "GetWatcherStatusPort",
    "ProcessTelemetryStreamPort",
    "SyncJournalSnapshotPort",
    "SnapshotSyncResultDTO",
    "StartMonitoringDTO",
    "WatcherStatusDTO",
)
