"""Unit tests for composition root bootstrapping."""

from ed_app.bootstrap import build_engine
from ed_domain.engine import TelemetryEngine
from ed_domain.ports.egress import EgressPort
from ed_domain.ports.watcher import WatcherPort


def test_build_engine_instantiation() -> None:
    """Verify that build_engine constructs a valid TelemetryEngine without side effects."""
    engine = build_engine()
    assert isinstance(engine, TelemetryEngine)
    assert isinstance(engine.watcher, WatcherPort)
    assert not engine.is_running

    assert len(engine.egress_ports) >= 1
    for egress in engine.egress_ports:
        assert isinstance(egress, EgressPort)


def test_engine_lifecycle_smoke() -> None:
    """Verify that engine starts and stops cleanly."""
    engine = build_engine()
    assert not engine.is_running

    engine.start()
    assert engine.is_running

    engine.stop()
    assert not engine.is_running
