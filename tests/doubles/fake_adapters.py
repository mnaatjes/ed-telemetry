"""In-memory test doubles satisfying HEXA-TRUTH-27."""

from __future__ import annotations

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
    FileIngestionEventDTO,
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


class FakeEgressAdapter(EgressPort):
    """In-memory test double for EgressPort satisfying HEXA-TRUTH-27."""

    def __init__(self) -> None:
        self.sent_payloads: list[TelemetryPayloadDTO] = []

    def send(self, payload: TelemetryPayloadDTO) -> None:
        self.sent_payloads.append(payload)
