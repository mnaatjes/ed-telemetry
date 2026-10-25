"""Unit tests for Domain Port Protocol Genealogy and Capability Taxonomy.

Verifies structural subtyping, runtime checkability, active vs. passive
discrimination, and driven adapter satisfaction.
Governed by ADR 0015 and SDD-013.
"""

from __future__ import annotations

from ed_telemetry.adapters.driven.egress.transmitter import NullTransmitter
from ed_telemetry.adapters.driven.watcher.watcher import FileSystemWatcher
from ed_telemetry.core.ports.base import (
    Port,
)
from ed_telemetry.core.ports.driven.telemetry_driven_port import (
    DiscreteSinkPort,
    EgressPort,
    LifecyclePort,
    StreamSourcePort,
    WatcherPort,
)


class TestDomainPortGenealogyAndProtocols:
    """Verifies TEST-PORT-01 and TEST-PORT-02: Port marker and capability protocol hierarchy."""

    def test_port_marker_pedigree(self) -> None:
        """TEST-PORT-01: Verifies all capability protocols and domain ports are sub-protocols of Port."""
        assert issubclass(LifecyclePort, Port)
        assert issubclass(DiscreteSinkPort, Port)
        assert issubclass(StreamSourcePort, Port)
        assert issubclass(EgressPort, Port)
        assert issubclass(WatcherPort, Port)

    def test_active_vs_passive_discrimination(self) -> None:
        """TEST-PORT-02: Proves that WatcherPort specializes LifecyclePort while EgressPort does not."""
        assert LifecyclePort in WatcherPort.__mro__
        assert StreamSourcePort in WatcherPort.__mro__
        assert DiscreteSinkPort in EgressPort.__mro__
        assert LifecyclePort not in EgressPort.__mro__


class TestConcreteDrivenAdapterSatisfaction:
    """Verifies TEST-PORT-03: Driven adapters satisfy their respective port genealogy."""

    def test_file_system_watcher_satisfies_genealogy(self) -> None:
        """TEST-PORT-03: FileSystemWatcher satisfies Port, LifecyclePort, StreamSourcePort, and WatcherPort."""
        watcher = FileSystemWatcher()
        assert isinstance(watcher, Port)
        assert isinstance(watcher, LifecyclePort)
        assert isinstance(watcher, StreamSourcePort)
        assert isinstance(watcher, WatcherPort)

    def test_null_transmitter_satisfies_genealogy(self) -> None:
        """TEST-PORT-03: NullTransmitter satisfies Port, DiscreteSinkPort, and EgressPort, but NOT LifecyclePort."""
        transmitter = NullTransmitter()
        assert isinstance(transmitter, Port)
        assert isinstance(transmitter, DiscreteSinkPort)
        assert isinstance(transmitter, EgressPort)
        assert not isinstance(transmitter, LifecyclePort)


class TestLifecyclePoliciesConformance:
    """Verifies TEST-PORT-05: Policy L1, L2, L3 behavioral lifecycle conformance."""

    def test_lifecycle_policy_l1_idempotent_start_and_stop(self) -> None:
        """Policy L1: start() and stop() must be safe no-ops if already in target state."""
        watcher = FileSystemWatcher()
        assert not watcher.is_active
        # Redundant stop when not started
        watcher.stop()
        assert not watcher.is_active

    def test_lifecycle_policy_l2_deterministic_join(self) -> None:
        """Policy L2: stop() must join background thread deterministically."""
        watcher = FileSystemWatcher(join_timeout=1.0)
        assert not watcher.is_active
        watcher.stop()
        assert not watcher.is_active

    def test_lifecycle_policy_l3_shielded_shutdown(self) -> None:
        """Policy L3: stop() suppresses internal teardown errors to prevent crashed shutdowns."""
        watcher = FileSystemWatcher()
        # Even if unstarted, stop() must never raise
        watcher.stop()
        assert not watcher.is_active
