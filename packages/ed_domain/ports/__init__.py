"""Ports definitions for ed_domain."""

from ed_domain.ports.egress import EgressPort
from ed_domain.ports.watcher import WatcherPort

__all__ = ["WatcherPort", "EgressPort"]
