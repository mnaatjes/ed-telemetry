"""In-memory test doubles satisfying HEXA-TRUTH-27."""

from __future__ import annotations

from datetime import UTC, datetime

from ed_telemetry.core.ports.driven.telemetry_driven_port import (
    AuditEventHandler,
    DiagnosticLogPort,
    DiscreteSinkPort,
    EgressPort,
    EventQueuePort,
    IngestionEventHandler,
    LifecyclePort,
    StreamSourcePort,
    TelemetryRepositoryPort,
    WatcherPort,
)
from ed_telemetry.core.ports.dto.telemetry_dto import (
    AuxiliarySnapshotDTO,
    DiagnosticLogRecordDTO,
    DiagnosticLogSnapshotDTO,
    FileIngestionEventDTO,
    GameStatusSnapshotDTO,
    HintSubmissionDTO,
    JournalCandidateDTO,
    JournalFileListDTO,
    JournalPathDTO,
    TelemetryBatchDTO,
    TelemetryPayloadDTO,
    TelemetryQueryDTO,
    TelemetryRecordDTO,
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


class FakeEventQueueAdapter(EventQueuePort):
    """In-memory test double for EventQueuePort satisfying HEXA-TRUTH-27."""

    def __init__(self, initial_events: list[TelemetryPayloadDTO] | None = None) -> None:
        self.queue: list[TelemetryPayloadDTO] = list(initial_events or [])
        self.dropped_count = 0

    def poll(self, timeout: float | None = None) -> TelemetryPayloadDTO | None:
        return self.queue.pop(0) if self.queue else None

    def get_batch(self, limit: int = 100, timeout: float | None = None) -> TelemetryBatchDTO:
        extracted = self.queue[:limit]
        self.queue = self.queue[limit:]
        return TelemetryBatchDTO(
            events=tuple(extracted),
            remaining_count=len(self.queue),
            dropped_count=self.dropped_count,
        )

    def queue_size(self) -> int:
        return len(self.queue)


class FakeTelemetryRepositoryAdapter(TelemetryRepositoryPort):
    """In-memory test double for TelemetryRepositoryPort."""

    def __init__(self) -> None:
        self.records: list[TelemetryRecordDTO] = []
        self._next_id = 1

    def insert_event(self, payload: TelemetryPayloadDTO) -> int:
        rid = self._next_id
        self._next_id += 1
        rec = TelemetryRecordDTO(
            id=rid,
            event_id=f"rec_{rid}",
            topic=payload.topic,
            timestamp=payload.timestamp,
            raw_hash=dict(payload.metadata).get("hash"),
            payload_json=payload.payload_bytes.decode("utf-8", errors="replace"),
            created_at=datetime.now(UTC),
        )
        self.records.append(rec)
        return rid

    def find_events(self, query: TelemetryQueryDTO) -> tuple[TelemetryRecordDTO, ...]:
        matched = self.records
        if query.since_id is not None:
            matched = [r for r in matched if r.id > query.since_id]
        if query.topic is not None:
            matched = [r for r in matched if r.topic == query.topic]
        return tuple(matched[: query.limit])

    def get_latest_event(self, topic: str) -> TelemetryRecordDTO | None:
        matched = [r for r in self.records if r.topic == topic]
        return matched[-1] if matched else None


class FakeDiagnosticLogAdapter(DiagnosticLogPort):
    """In-memory test double for DiagnosticLogPort."""

    def __init__(self, records: list[DiagnosticLogRecordDTO] | None = None) -> None:
        self.records: list[DiagnosticLogRecordDTO] = list(records or [])

    def get_recent_logs(
        self,
        min_level: str | None = None,
        limit: int = 100,
    ) -> DiagnosticLogSnapshotDTO:
        weights = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        threshold = weights.get(min_level.upper(), 0) if min_level else 0
        matched = self.records
        if threshold > 0:
            matched = [r for r in matched if weights.get(r.level.upper(), 0) >= threshold]
        selected = tuple(matched[-limit:])
        return DiagnosticLogSnapshotDTO(
            records=selected,
            total_retained=len(selected),
        )
