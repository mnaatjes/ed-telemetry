"""Use case for managing continuous inbound telemetry stream processing."""

from __future__ import annotations

import json

from ..ports.driven.telemetry_driven_port import (
    EgressPort,
    WatcherPort,
)
from ..ports.driving.telemetry_port import ProcessTelemetryStreamPort, StartMonitoringDTO
from ..ports.dto.telemetry_dto import (
    FileIngestionEventDTO,
    TelemetryPayloadDTO,
    WatcherAuditEventDTO,
)


class ProcessTelemetryStreamUseCase(ProcessTelemetryStreamPort):
    """Stateless interactor coordinating stream ingestion and egress dispatch."""

    def __init__(self, watcher: WatcherPort, egress: EgressPort) -> None:
        self._watcher = watcher
        self._egress = egress
        self._watcher.register_event_handler(self._handle_ingestion_event)
        self._watcher.register_audit_handler(self._handle_audit_event)

    def start_streaming(self, command: StartMonitoringDTO | None = None) -> None:
        """Start the background telemetry watcher worker."""
        self._watcher.start()

    def stop_streaming(self) -> None:
        """Stop the background telemetry watcher worker."""
        self._watcher.stop()

    def _handle_ingestion_event(self, event: FileIngestionEventDTO) -> None:
        """Normalize raw file ingestion event into outbound telemetry payload."""
        payload = TelemetryPayloadDTO(
            topic=f"telemetry.{event.file_kind}",
            timestamp=event.timestamp,
            payload_bytes=event.raw_payload,
            metadata=(("hash", event.raw_hash), ("path", str(event.target_path))),
        )
        self._egress.send(payload)

        # Emit lightweight claim-check delta notification for companion files
        if event.file_kind in ("status", "snapshot"):
            from pathlib import Path

            target_filename = Path(event.target_path).name
            delta_dict = {
                "topic": "telemetry.file_delta",
                "target": target_filename,
                "action": "modified",
                "raw_hash": event.raw_hash,
                "timestamp": event.timestamp.isoformat(),
            }
            delta_payload = TelemetryPayloadDTO(
                topic="telemetry.file_delta",
                timestamp=event.timestamp,
                payload_bytes=json.dumps(delta_dict).encode("utf-8"),
                metadata=(("target", target_filename), ("hash", event.raw_hash)),
            )
            self._egress.send(delta_payload)

    def _handle_audit_event(self, event: WatcherAuditEventDTO) -> None:
        """Normalize watcher audit/error event into telemetry.audit payload."""
        event_dict = {
            "timestamp": event.timestamp.isoformat(),
            "action": event.action,
            "target_path": event.target_path,
            "detail": event.detail,
        }
        payload = TelemetryPayloadDTO(
            topic="telemetry.audit",
            timestamp=event.timestamp,
            payload_bytes=json.dumps(event_dict).encode("utf-8"),
            metadata=(("action", event.action),),
        )
        self._egress.send(payload)
