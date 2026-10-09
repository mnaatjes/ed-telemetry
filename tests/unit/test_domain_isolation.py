"""Unit tests verifying pure domain isolation per ADR 0001 Section 6.2."""

import sys


def test_domain_clean_isolation() -> None:
    """Verify domain imports cleanly without importing sibling packages."""
    # Ensure sibling modules are not loaded
    sibling_prefixes = ("infrastructure.watcher", "infrastructure.egress", "sdk", "services")
    for mod in list(sys.modules.keys()):
        if any(mod.startswith(prefix) for prefix in sibling_prefixes):
            del sys.modules[mod]

    # Import domain in isolation
    import domain
    from domain.engine import TelemetryEngine
    from domain.ports.egress import EgressPort
    from domain.ports.watcher import WatcherPort

    # Assert exports exist and are valid types
    assert domain.__name__ == "domain"
    assert TelemetryEngine is not None
    assert issubclass(WatcherPort, object)
    assert issubclass(EgressPort, object)

    # Assert no sibling packages were loaded as a consequence of importing domain
    for mod in sys.modules:
        assert not any(mod.startswith(prefix) for prefix in sibling_prefixes), (
            f"Sibling package '{mod}' was unexpectedly imported by domain"
        )
