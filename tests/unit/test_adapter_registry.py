"""Unit tests for Driven Adapter Registry Subsystem.

Verifies BaseAdapterRegistry, EgressRegistry, and WatcherRegistry conformance,
driven adapter boundary reflection enforcement, and cardinality semantics.
Governed by ADR 0014 and SDD-012.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from infrastructure.egress.transmitter import NullTransmitter
from infrastructure.watcher.watcher import FileSystemWatcher
from services.registry.base import BaseAdapterRegistry
from services.registry.egress import EgressRegistry
from services.registry.watcher import WatcherRegistry


class TestBaseAdapterRegistry:
    """Verifies TEST-REG-01, TEST-REG-02, TEST-REG-03 for BaseAdapterRegistry."""

    def test_rejects_non_infrastructure_adapter_module(self) -> None:
        """TEST-REG-01: Verifies that registry rejects instances not in src/infrastructure/."""
        registry: BaseAdapterRegistry[Any] = BaseAdapterRegistry()

        class FakeAdapter:
            pass

        with pytest.raises(TypeError, match="Adapter Registry only accepts Driven Adapters"):
            registry.register("fake", FakeAdapter())

    def test_rejects_duplicate_or_invalid_key(self) -> None:
        """TEST-REG-02: Verifies non-empty string keys and rejection of duplicate keys."""
        registry: BaseAdapterRegistry[Any] = BaseAdapterRegistry()
        adapter = NullTransmitter()

        with pytest.raises(ValueError, match="non-empty string"):
            registry.register("", adapter)

        registry.register("transmitter_1", adapter)

        with pytest.raises(KeyError, match="already registered"):
            registry.register("transmitter_1", adapter)

    def test_dictionary_protocol_and_ordering(self) -> None:
        """TEST-REG-03: Verifies get, get_all, list_keys, len, and container operations."""
        registry: BaseAdapterRegistry[Any] = BaseAdapterRegistry()
        adapter1 = NullTransmitter()
        adapter2 = NullTransmitter()

        assert len(registry) == 0
        assert "null_1" not in registry

        registry.register("null_1", adapter1)
        registry.register("null_2", adapter2)

        assert len(registry) == 2
        assert "null_1" in registry
        assert "null_2" in registry
        assert registry.get("null_1") is adapter1
        assert registry.get("null_2") is adapter2
        assert registry.list_keys() == ("null_1", "null_2")
        assert registry.get_all() == (adapter1, adapter2)
        assert list(registry) == ["null_1", "null_2"]

        with pytest.raises(KeyError, match="No adapter registered under key"):
            registry.get("non_existent")


class TestEgressRegistry:
    """Verifies TEST-REG-04 for EgressRegistry broadcast and transmitter querying."""

    def test_broadcast_and_get_transmitters(self) -> None:
        """TEST-REG-04: Verifies get_transmitters and broadcast dispatch to all registered sinks."""
        registry = EgressRegistry()

        class DummyTransmitter:
            __module__ = "infrastructure.egress.dummy"

            def __init__(self) -> None:
                self.received: list[Mapping[str, Any]] = []

            def send(self, payload: Mapping[str, Any]) -> None:
                self.received.append(payload)

        sink1 = DummyTransmitter()
        sink2 = DummyTransmitter()

        registry.register("sink1", sink1)
        registry.register("sink2", sink2)

        assert registry.get_transmitters() == (sink1, sink2)

        test_payload = {"event": "Docked", "station": "Jameson"}
        registry.broadcast(test_payload)

        assert sink1.received == [test_payload]
        assert sink2.received == [test_payload]


class TestWatcherRegistry:
    """Verifies TEST-REG-05 for WatcherRegistry active selection mechanics."""

    def test_active_selection_lifecycle(self) -> None:
        """TEST-REG-05: Verifies automatic default activation and manual set_active switching."""
        registry = WatcherRegistry()
        assert registry.active_key is None

        with pytest.raises(KeyError, match="No active watcher configured"):
            registry.get_active()

        watcher1 = FileSystemWatcher()
        watcher2 = FileSystemWatcher()

        registry.register("primary", watcher1)
        assert registry.active_key == "primary"
        assert registry.get_active() is watcher1

        registry.register("secondary", watcher2)
        # Should stay on primary unless explicitly switched
        assert registry.active_key == "primary"
        assert registry.get_active() is watcher1

        registry.set_active("secondary")
        assert registry.active_key == "secondary"
        assert registry.get_active() is watcher2

        with pytest.raises(KeyError, match="Cannot activate unregistered watcher"):
            registry.set_active("nonexistent")
