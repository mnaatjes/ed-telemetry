"""Test doubles package exports."""

from .fake_adapters import (
    FakeDiscreteSinkAdapter,
    FakeEgressAdapter,
    FakeLifecycleAdapter,
    FakeStreamSourceAdapter,
    FakeWatcherAdapter,
)

__all__ = (
    "FakeDiscreteSinkAdapter",
    "FakeEgressAdapter",
    "FakeLifecycleAdapter",
    "FakeStreamSourceAdapter",
    "FakeWatcherAdapter",
)
