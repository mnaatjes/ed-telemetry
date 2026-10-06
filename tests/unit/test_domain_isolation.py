"""Unit tests verifying pure domain isolation per ADR 0001 Section 6.2."""

import sys


def test_domain_clean_isolation() -> None:
    """Verify ed_domain imports cleanly without importing sibling packages."""
    # Ensure sibling modules are not loaded
    sibling_prefixes = ("ed_watcher", "ed_egress", "ed_sdk", "ed_app")
    for mod in list(sys.modules.keys()):
        if any(mod.startswith(prefix) for prefix in sibling_prefixes):
            del sys.modules[mod]

    # Import ed_domain in isolation
    import ed_domain
    from ed_domain.engine import TelemetryEngine
    from ed_domain.ports.egress import EgressPort
    from ed_domain.ports.watcher import WatcherPort

    # Assert exports exist and are valid types
    assert ed_domain.__name__ == "ed_domain"
    assert TelemetryEngine is not None
    assert issubclass(WatcherPort, object)
    assert issubclass(EgressPort, object)

    # Assert no sibling packages were loaded as a consequence of importing ed_domain
    for mod in sys.modules:
        assert not any(
            mod.startswith(prefix) for prefix in sibling_prefixes
        ), f"Sibling package '{mod}' was unexpectedly imported by ed_domain"
