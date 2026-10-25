"""Test doubles package exports."""

from .fake_egress_adapter import FakeEgressAdapter
from .fake_watcher_adapter import FakeWatcherAdapter

__all__ = ["FakeWatcherAdapter", "FakeEgressAdapter"]
