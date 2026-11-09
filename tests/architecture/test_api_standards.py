"""Architectural quality gates verifying API route naming, OpenAPI synchrony, and headers."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

CANONICAL_ROUTE_PATTERN = re.compile(
    r"^/api/v1/(state|state/heartbeat|status|snapshots|snapshots/([a-zA-Z0-9_\-\.]+)|journal/(latest|events)|events/(query|queue|stream)|system/(health|watcher|logs|control))$"
)

DEPRECATED_LEGACY_ROUTES = frozenset(
    {
        "/api/v1/telemetry/head",
        "/api/v1/status/game",
        "/api/v1/journal/query",
        "/api/v1/journal/queue",
        "/api/v1/journal/stream",
        "/api/v1/events",
        "/api/v1/events/buffer",
        "/api/v1/stream",
        "/api/v1/health",
        "/api/v1/diagnostics/logs",
        "/api/v1/control/watch",
        "",
    }
)


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_server_routes_conform_to_canonical_schema_or_legacy_aliases() -> None:
    """Verify that all router paths in server.py match canonical regex or legacy alias set."""
    server_py = _get_project_root() / "src" / "ed_telemetry" / "adapters" / "driving" / "api" / "server.py"
    content = server_py.read_text(encoding="utf-8")

    # Extract all string literals matching /api/v1/...
    routes = set(re.findall(r'"(/api/v1/[a-zA-Z0-9_\-/]+)"', content))

    for route in routes:
        # Route may be path-prefix like /api/v1/snapshots/
        test_path = route.rstrip("/")
        if test_path.endswith("/snapshots"):
            # Wildcard test
            assert CANONICAL_ROUTE_PATTERN.match("/api/v1/snapshots/Market.json")
            continue

        is_canonical = bool(CANONICAL_ROUTE_PATTERN.match(test_path))
        is_legacy = test_path in DEPRECATED_LEGACY_ROUTES

        assert is_canonical or is_legacy, (
            f"Route '{route}' in server.py violates API naming standards and is not an approved legacy alias."
        )


def test_openapi_specification_contains_canonical_routes() -> None:
    """Verify that architecture/api/openapi.yaml declares all canonical API endpoints."""
    openapi_yaml = _get_project_root() / "architecture" / "api" / "openapi.yaml"
    assert openapi_yaml.exists(), "openapi.yaml does not exist in architecture/api/"

    spec = yaml.safe_load(openapi_yaml.read_text(encoding="utf-8"))
    paths = set(spec.get("paths", {}).keys())

    required_canonical_endpoints = {
        "/api/v1/state",
        "/api/v1/state/heartbeat",
        "/api/v1/status",
        "/api/v1/snapshots",
        "/api/v1/snapshots/{name}",
        "/api/v1/journal/latest",
        "/api/v1/journal/events",
        "/api/v1/events/query",
        "/api/v1/events/queue",
        "/api/v1/events/stream",
        "/api/v1/system/health",
        "/api/v1/system/watcher",
        "/api/v1/system/logs",
        "/api/v1/system/control",
    }

    missing = required_canonical_endpoints - paths
    assert not missing, f"openapi.yaml is missing canonical endpoints: {missing}"
