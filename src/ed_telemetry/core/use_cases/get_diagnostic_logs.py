"""Use case for retrieving diagnostic application log snapshots."""

from __future__ import annotations

from ..ports.driven.telemetry_driven_port import DiagnosticLogPort
from ..ports.driving.telemetry_port import GetDiagnosticLogsPort
from ..ports.dto.telemetry_dto import DiagnosticLogSnapshotDTO


class GetDiagnosticLogsUseCase(GetDiagnosticLogsPort):
    """Retrieves buffered diagnostic log snapshots with optional filtering."""

    def __init__(self, log_port: DiagnosticLogPort) -> None:
        self._log_port = log_port

    def get_logs(
        self,
        min_level: str | None = None,
        limit: int = 100,
    ) -> DiagnosticLogSnapshotDTO:
        return self._log_port.get_recent_logs(min_level=min_level, limit=limit)
