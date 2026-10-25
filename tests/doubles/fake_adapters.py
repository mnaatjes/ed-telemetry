"""In-memory test doubles satisfying HEXA-TRUTH-27."""

from __future__ import annotations

from datetime import UTC, datetime

from ed_telemetry.core.ports.driven.telemetry_driven_port import (
    AuditEventHandler,
    DiscreteSinkPort,
    EgressPort,
    IngestionEventHandler,
    LifecyclePort,
    StreamSourcePort,
    WatcherPort,
)
from ed_telemetry.core.ports.dto.telemetry_dto import (
    AuxiliarySnapshotDTO,
    FileIngestionEventDTO,
    GameStatusSnapshotDTO,
    HintSubmissionDTO,
    JournalCandidateDTO,
    JournalFileListDTO,
    JournalPathDTO,
    TelemetryPayloadDTO,
    WatcherAuditEventDTO,
)


class FakeLifecycleAdapter(LifecyclePort):
    """In-memory double for LifecyclePort."""

    def __init__(self) -> None:
        self._is_active = False

    def start(self) -> None:
        self._is_active = True

    def stop(self) -> None:
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active


class FakeStreamSourceAdapter(StreamSourcePort):
    """In-memory double for StreamSourcePort."""

    def __init__(self) -> None:
        self._event_handlers: list[IngestionEventHandler] = []
        self._audit_handlers: list[AuditEventHandler] = []

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        self._event_handlers.append(handler)

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        self._audit_handlers.append(handler)


class FakeDiscreteSinkAdapter(DiscreteSinkPort):
    """In-memory double for DiscreteSinkPort."""

    def __init__(self) -> None:
        self.sent_payloads: list[TelemetryPayloadDTO] = []

    def send(self, payload: TelemetryPayloadDTO) -> None:
        self.sent_payloads.append(payload)


class FakeWatcherAdapter(WatcherPort):
    """In-memory test double for WatcherPort satisfying HEXA-TRUTH-27."""

    def __init__(self, journal_dir: str | None = None) -> None:
        self._journal_dir = journal_dir
        self._is_active = False
        self._event_handlers: list[IngestionEventHandler] = []
        self._audit_handlers: list[AuditEventHandler] = []

    def start(self) -> None:
        self._is_active = True

    def stop(self) -> None:
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def journal_dir(self) -> str | None:
        return self._journal_dir

    def register_event_handler(self, handler: IngestionEventHandler) -> None:
        self._event_handlers.append(handler)

    def register_audit_handler(self, handler: AuditEventHandler) -> None:
        self._audit_handlers.append(handler)

    def emit_test_event(self, event: FileIngestionEventDTO) -> None:
        for handler in self._event_handlers:
            handler(event)

    def emit_test_audit(self, event: WatcherAuditEventDTO) -> None:
        for handler in self._audit_handlers:
            handler(event)

    def discover_path(self, override_path: str | None = None) -> JournalPathDTO:
        resolved = override_path or self._journal_dir or "/fake/journal/dir"
        return JournalPathDTO(
            resolved_path=resolved,
            platform="linux",
            discovery_source="fake_test_double",
        )

    def list_journals(self) -> JournalFileListDTO:
        target_dir = self._journal_dir or "/fake/journal/dir"
        candidates = (
            JournalCandidateDTO(
                filename="Journal.2026-10-25T000000.01.log",
                path=f"{target_dir}/Journal.2026-10-25T000000.01.log",
                timestamp=datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC),
                part=1,
                mtime=1729814400.0,
                is_standard_format=True,
            ),
        )
        return JournalFileListDTO(
            journal_dir=target_dir,
            candidates=candidates,
            active_journal=candidates[0].filename,
        )

    def read_status_snapshot(self) -> GameStatusSnapshotDTO:
        return GameStatusSnapshotDTO(
            exists=True,
            target_path=f"{self._journal_dir or '/fake/journal/dir'}/Status.json",
            timestamp=datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC),
            raw_payload=b'{"Flags": 16842765, "Pips": [4, 8, 0], "FireGroup": 0}',
            raw_hash="fake_status_hash",
        )

    def read_auxiliary_snapshot(self, name: str) -> AuxiliarySnapshotDTO:
        return AuxiliarySnapshotDTO(
            target_name=name,
            exists=True,
            target_path=f"{self._journal_dir or '/fake/journal/dir'}/{name}",
            timestamp=datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC),
            raw_payload=b'{"timestamp":"2026-10-25T00:00:00Z","event":"NavRoute","Route":[]}',
            raw_hash="fake_aux_hash",
        )

    def submit_ingest_hint(self, action: str, target_name: str | None = None) -> HintSubmissionDTO:
        return HintSubmissionDTO(
            action=action,
            target_name=target_name,
            accepted=True,
            detail="Hint accepted by fake double",
        )


class FakeEgressAdapter(EgressPort):
    """In-memory test double for EgressPort satisfying HEXA-TRUTH-27."""

    def __init__(self) -> None:
        self.sent_payloads: list[TelemetryPayloadDTO] = []

    def send(self, payload: TelemetryPayloadDTO) -> None:
        self.sent_payloads.append(payload)
