"""Ports definitions for domain."""

from domain.ports.egress import EgressPort
from domain.ports.watcher import WatcherPort

__all__ = ["WatcherPort", "EgressPort"]
