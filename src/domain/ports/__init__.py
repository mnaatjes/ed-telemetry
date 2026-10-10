"""Domain port contracts and capability protocols."""

from domain.ports.base import (
    AuditEventHandler,
    ConnectionPort,
    DiscreteSinkPort,
    IngestionEventHandler,
    LifecyclePort,
    Port,
    StreamSourcePort,
    TransactionalPort,
)
from domain.ports.egress import EgressPort
from domain.ports.watcher import WatcherPort

__all__ = [
    "AuditEventHandler",
    "ConnectionPort",
    "DiscreteSinkPort",
    "EgressPort",
    "IngestionEventHandler",
    "LifecyclePort",
    "Port",
    "StreamSourcePort",
    "TransactionalPort",
    "WatcherPort",
]
