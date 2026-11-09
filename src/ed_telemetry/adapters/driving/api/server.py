"""Driving adapter providing a zero-dependency HTTP and SSE server."""

from __future__ import annotations

import hmac
import json
import os
import re
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ed_telemetry.adapters.paths import resolve_default_credentials_path
from ed_telemetry.core.ports.driving.telemetry_port import (
    FindJournalPathPort,
    FindTelemetryEventsPort,
    GetAuxiliarySnapshotPort,
    GetDiagnosticLogsPort,
    GetJournalFilesPort,
    GetLatestGameStatusPort,
    GetStateHeartbeatPort,
    GetTelemetryEventsPort,
    GetTelemetryHeadPort,
    GetTelemetryStatePort,
    GetTelemetryStreamPort,
    GetWatcherStatusPort,
    ProcessTelemetryStreamPort,
    TelemetryQueryDTO,
)

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost",
    "http://127.0.0.1",
    "http://[::1]",
)

LOOPBACK_ORIGIN_REGEX = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")


def _parse_clamped_limit(
    query: dict[str, list[str]],
    default: int = 100,
    min_val: int = 1,
    max_val: int = 500,
) -> int:
    """Parse and clamp integer limit query parameter within safe operational bounds."""
    if "limit" not in query:
        return default
    try:
        val = int(query["limit"][0])
        return max(min_val, min(val, max_val))
    except (ValueError, IndexError):
        return default


class DynamicCredentialProvider:
    """Thread-safe credential resolver caching and hot-reloading tokens via file mtime tracking."""

    def __init__(
        self,
        static_override: str | None = None,
        credentials_path: Path | None = None,
    ) -> None:
        self.static_override = static_override.strip() if static_override else None
        self._credentials_path = credentials_path or resolve_default_credentials_path()
        self._lock = threading.Lock()
        self._cached_mtime_ns: int | None = None
        self._cached_file_key: str | None = None

    def __call__(self) -> str | None:
        return self.resolve()

    def resolve(self) -> str | None:
        """Resolve current API key following precedence: static override -> env -> credentials file."""
        if self.static_override:
            return self.static_override

        env_key = os.environ.get("ED_API_KEY")
        if env_key:
            return env_key.strip()

        with self._lock:
            try:
                stat_res = self._credentials_path.stat()
                current_mtime = stat_res.st_mtime_ns
                if current_mtime != self._cached_mtime_ns:
                    with open(self._credentials_path, encoding="utf-8") as fp:
                        data = json.load(fp)
                        key = data.get("api_key")
                        self._cached_file_key = key.strip() if isinstance(key, str) else None
                    self._cached_mtime_ns = current_mtime
                return self._cached_file_key
            except (OSError, json.JSONDecodeError):
                self._cached_mtime_ns = None
                self._cached_file_key = None
                return None


class SSEConnectionTracker:
    """Thread-safe active SSE client tracker with concurrency ceiling."""

    def __init__(self, max_clients: int = 16) -> None:
        self.max_clients = max_clients
        self._lock = threading.Lock()
        self._active_clients = 0

    def acquire(self) -> bool:
        """Attempt to acquire a stream slot. Returns True if granted."""
        with self._lock:
            if self._active_clients >= self.max_clients:
                return False
            self._active_clients += 1
            return True

    def release(self) -> None:
        """Release a stream slot upon client disconnect."""
        with self._lock:
            if self._active_clients > 0:
                self._active_clients -= 1

    @property
    def active_count(self) -> int:
        """Current number of connected streaming clients."""
        with self._lock:
            return self._active_clients


class TelemetryHttpHandler(BaseHTTPRequestHandler):
    """Request handler dispatching REST and SSE requests to driving use case ports."""

    # Injected by server
    watcher_status_port: GetWatcherStatusPort
    process_stream_port: ProcessTelemetryStreamPort
    find_events_port: FindTelemetryEventsPort
    get_events_port: GetTelemetryEventsPort
    stream_events_port: GetTelemetryStreamPort

    game_status_port: GetLatestGameStatusPort
    journal_path_port: FindJournalPathPort
    journal_files_port: GetJournalFilesPort
    aux_snapshot_port: GetAuxiliarySnapshotPort
    diagnostic_logs_port: GetDiagnosticLogsPort | None
    telemetry_head_port: GetTelemetryHeadPort | None = None
    telemetry_state_port: GetTelemetryStatePort | None = None
    state_heartbeat_port: GetStateHeartbeatPort | None = None

    server_api_key: str | None = None
    api_key_resolver: Callable[[], str | None] | None = None
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    sse_tracker: SSEConnectionTracker | None = None

    def _resolve_expected_key(self) -> str | None:
        """Resolve current active API key from dynamic resolver or static property."""
        if self.api_key_resolver is not None:
            return self.api_key_resolver()
        return self.server_api_key

    def _authenticate_request(self) -> bool:
        """Authenticate request using constant-time token comparison if API key is configured."""
        expected_key = self._resolve_expected_key()
        if not expected_key:
            return True

        # 1. Check Bearer token
        auth_hdr = self.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
            if hmac.compare_digest(token, expected_key):
                return True

        # 2. Check X-API-Key header
        api_key_hdr = self.headers.get("X-API-Key", "")
        if api_key_hdr and hmac.compare_digest(api_key_hdr, expected_key):
            return True

        # 3. Check query param for SSE EventSource / browser clients
        parsed_query = parse_qs(urlparse(self.path).query)
        if "api_key" in parsed_query:
            query_token = parsed_query["api_key"][0]
            if hmac.compare_digest(query_token, expected_key):
                return True

        self._send_problem(
            status_code=401,
            title="Unauthorized",
            detail="Invalid or missing API key.",
            instance=self.path,
        )
        return False

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if an Origin header is permitted under the CORS policy."""
        if not origin:
            return False
        if LOOPBACK_ORIGIN_REGEX.match(origin):
            return True
        for allowed in self.allowed_origins:
            if origin == allowed or origin.startswith(f"{allowed}:"):
                return True
        return False

    def _apply_cors_headers(self) -> None:
        """Apply CORS headers if origin is permitted."""
        origin = self.headers.get("Origin")
        if origin and self._is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Authorization, X-API-Key, Content-Type",
            )
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._apply_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle incoming GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        # 1. System Health: /api/v1/system/health (Canonical) & /api/v1/health (Legacy)
        if path in ("", "/api/v1/health", "/api/v1/system/health"):
            self._send_json(
                200,
                {"status": "ok", "service": "ed-telemetry"},
                source="memory-buffer",
                plane="system",
            )
            return

        if not self._authenticate_request():
            return

        # 2. State Hydration: /api/v1/state (Canonical) & /api/v1/telemetry/head (Legacy)
        if path in ("/api/v1/state", "/api/v1/telemetry/head"):
            port = self.telemetry_state_port or self.telemetry_head_port
            if not port:
                self._send_problem(
                    status_code=503,
                    title="Service Unavailable",
                    detail="Telemetry state port is not configured.",
                    instance=path,
                    source="memory-buffer",
                    plane="state",
                )
                return
            state_dto = port.get_state() if hasattr(port, "get_state") else port.get_head()
            etag = f'W/"{state_dto.state_sequence}"'
            self._send_json(
                200,
                asdict(state_dto),
                source="memory-buffer",
                plane="state",
                etag=etag,
            )
            return

        # 3. State Heartbeat: /api/v1/state/heartbeat (Canonical)
        if path == "/api/v1/state/heartbeat":
            if not self.state_heartbeat_port:
                self._send_problem(
                    status_code=503,
                    title="Service Unavailable",
                    detail="State heartbeat port is not configured.",
                    instance=path,
                    source="memory-buffer",
                    plane="state",
                )
                return
            heartbeat_dto = self.state_heartbeat_port.get_heartbeat()
            etag = f'W/"{heartbeat_dto.state_sequence}"'
            self._send_json(
                200,
                asdict(heartbeat_dto),
                source="memory-buffer",
                plane="state",
                etag=etag,
            )
            return

        # 4. Status.json: /api/v1/status/game
        if path == "/api/v1/status/game":
            if not self.game_status_port:
                self._send_problem(
                    status_code=503,
                    title="Service Unavailable",
                    detail="Game status port is not configured.",
                    instance=path,
                    source="memory-buffer",
                    plane="status",
                )
                return
            snap = self.game_status_port.get_game_status()
            etag_status: str | None = f'W/"{snap.raw_hash}"' if snap.raw_hash else None
            self._send_json(
                200,
                asdict(snap),
                source="memory-buffer",
                plane="status",
                etag=etag_status,
            )
            return

        # 4b. Watcher Status: /api/v1/system/watcher (Canonical) & /api/v1/status (Legacy)
        if path in ("/api/v1/system/watcher", "/api/v1/status"):
            if not self.watcher_status_port:
                self._send_problem(
                    status_code=503,
                    title="Service Unavailable",
                    detail="Watcher status port is not configured.",
                    instance=path,
                    source="memory-buffer",
                    plane="system",
                )
                return
            status_dto = self.watcher_status_port.get_status()
            self._send_json(
                200,
                asdict(status_dto),
                source="memory-buffer",
                plane="system",
            )
            return

        # 5. Snapshots Map: /api/v1/snapshots
        if path == "/api/v1/snapshots":
            snapshots_dict = {}
            for name in (
                "Market.json",
                "Outfitting.json",
                "Shipyard.json",
                "ModulesInfo.json",
                "Cargo.json",
                "Backpack.json",
                "NavRoute.json",
                "ShipLocker.json",
                "FCMaterials.json",
            ):
                try:
                    s = self.aux_snapshot_port.get_snapshot(name)
                    if s.exists:
                        snapshots_dict[name.replace(".json", "")] = asdict(s)
                except Exception:
                    continue
            self._send_json(
                200,
                snapshots_dict,
                source="memory-buffer",
                plane="snapshots",
            )
            return

        # 6. Specific Snapshot: /api/v1/snapshots/{name}
        if path.startswith("/api/v1/snapshots/"):
            snapshot_name = path[len("/api/v1/snapshots/") :]
            if not snapshot_name.endswith(".json"):
                snapshot_name = f"{snapshot_name}.json"
            try:
                aux_snap = self.aux_snapshot_port.get_snapshot(snapshot_name)
            except Exception:
                self._send_problem(
                    status_code=404,
                    title="Snapshot Not Found",
                    detail=f"Auxiliary game snapshot '{snapshot_name}' is not recognized or does not exist.",
                    instance=path,
                    source="memory-buffer",
                    plane="snapshots",
                )
                return

            if not aux_snap.exists:
                self._send_problem(
                    status_code=404,
                    title="Snapshot Not Found",
                    detail=f"Auxiliary game snapshot '{snapshot_name}' does not exist.",
                    instance=path,
                    source="memory-buffer",
                    plane="snapshots",
                )
                return
            etag_aux: str | None = f'W/"{aux_snap.raw_hash}"' if aux_snap.raw_hash else None
            self._send_json(
                200,
                asdict(aux_snap),
                source="memory-buffer",
                plane="snapshots",
                etag=etag_aux,
            )
            return

        # 7. Journal Latest: /api/v1/journal/latest
        if path == "/api/v1/journal/latest":
            if hasattr(self, "telemetry_state_port") and self.telemetry_state_port:
                st = self.telemetry_state_port.get_state()
                rec = st.latest_journal_event
            elif self.telemetry_head_port:
                st = self.telemetry_head_port.get_head()
                rec = st.latest_journal_event
            else:
                rec = None
            self._send_json(
                200,
                asdict(rec) if rec is not None else None,
                source="memory-buffer",
                plane="journal",
            )
            return

        # 8. Journal Query: /api/v1/journal/query (Canonical) & /api/v1/events (Legacy)
        if path in ("/api/v1/journal/query", "/api/v1/events"):
            since_id = int(query["since_id"][0]) if "since_id" in query else None
            topic = query["topic"][0] if "topic" in query else None
            order = (
                query["order"][0].lower()
                if "order" in query and query["order"][0].lower() in ("asc", "desc")
                else "asc"
            )
            limit = _parse_clamped_limit(query, default=100, min_val=1, max_val=500)
            q_dto = TelemetryQueryDTO(since_id=since_id, topic=topic, limit=limit, order=order)
            records = self.find_events_port.find_events(q_dto)
            self._send_json(
                200,
                [asdict(r) for r in records],
                source="sqlite-wal",
                plane="journal",
            )
            return

        # 9. Journal Queue: /api/v1/journal/queue (Canonical) & /api/v1/events/buffer (Legacy)
        if path in ("/api/v1/journal/queue", "/api/v1/events/buffer"):
            limit = _parse_clamped_limit(query, default=100, min_val=1, max_val=500)
            batch = self.get_events_port.get_events(limit=limit)
            self._send_json(
                200,
                asdict(batch),
                source="memory-buffer",
                plane="journal",
            )
            return

        # 10. Journal Stream: /api/v1/journal/stream (Canonical) & /api/v1/stream (Legacy)
        if path in ("/api/v1/journal/stream", "/api/v1/stream"):
            self._handle_sse_stream()
            return

        # 11. System Watcher: /api/v1/system/watcher
        if path == "/api/v1/system/watcher":
            status_dto = self.watcher_status_port.get_status()
            self._send_json(
                200,
                asdict(status_dto),
                source="memory-buffer",
                plane="system",
            )
            return

        # 12. System Logs: /api/v1/system/logs (Canonical) & /api/v1/diagnostics/logs (Legacy)
        if path in ("/api/v1/system/logs", "/api/v1/diagnostics/logs"):
            if not self.diagnostic_logs_port:
                self._send_problem(
                    status_code=503,
                    title="Service Unavailable",
                    detail="Diagnostic log port is not configured.",
                    instance=path,
                    source="memory-buffer",
                    plane="system",
                )
                return
            min_level = query["min_level"][0] if "min_level" in query else None
            limit = _parse_clamped_limit(query, default=100, min_val=1, max_val=500)
            snapshot = self.diagnostic_logs_port.get_logs(min_level=min_level, limit=limit)
            self._send_json(
                200,
                asdict(snapshot),
                source="memory-buffer",
                plane="system",
            )
            return

        self._send_problem(
            status_code=404,
            title="Not Found",
            detail=f"Resource '{path}' does not exist on this server.",
            instance=path,
            source="memory-buffer",
            plane="system",
        )

    def do_POST(self) -> None:
        """Handle incoming POST requests."""
        if not self._authenticate_request():
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # System Control: /api/v1/system/control (Canonical) & /api/v1/control/watch (Legacy)
        if path in ("/api/v1/system/control", "/api/v1/control/watch"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError:
                self._send_problem(
                    status_code=400,
                    title="Bad Request",
                    detail="Invalid JSON body provided.",
                    instance=path,
                    source="memory-buffer",
                    plane="system",
                )
                return

            action = data.get("action", "start")
            if action == "start":
                self.process_stream_port.start_streaming()
                self._send_json(
                    200,
                    {"action": "start", "result": "started"},
                    source="memory-buffer",
                    plane="system",
                )
            elif action == "stop":
                self.process_stream_port.stop_streaming()
                self._send_json(
                    200,
                    {"action": "stop", "result": "stopped"},
                    source="memory-buffer",
                    plane="system",
                )
            else:
                self._send_problem(
                    status_code=400,
                    title="Bad Request",
                    detail=f"Unknown control action: '{action}'. Expected 'start' or 'stop'.",
                    instance=path,
                    source="memory-buffer",
                    plane="system",
                )
            return

        self._send_problem(
            status_code=404,
            title="Not Found",
            detail=f"Endpoint '{path}' does not accept POST requests.",
            instance=path,
            source="memory-buffer",
            plane="system",
        )

    def _handle_sse_stream(self) -> None:
        """Serve Server-Sent Events (SSE) live feed with connection limit guardrail."""
        if self.sse_tracker and not self.sse_tracker.acquire():
            self._send_problem(
                status_code=429,
                title="Too Many Requests",
                detail=f"Maximum concurrent SSE stream limit reached ({self.sse_tracker.max_clients} clients).",
                instance=self.path,
            )
            return

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._apply_cors_headers()
            self.end_headers()

            # Send initial connected heartbeat
            self.wfile.write(b'data: {"event":"connected"}\n\n')
            self.wfile.flush()

            try:
                for payload in self.stream_events_port.stream_events(timeout=0.5):
                    if payload.topic == "telemetry.file_delta":
                        try:
                            msg = json.loads(payload.payload_bytes.decode("utf-8"))
                        except Exception:
                            msg = {
                                "topic": payload.topic,
                                "timestamp": payload.timestamp.isoformat(),
                                "payload": payload.payload_bytes.decode("utf-8", errors="replace"),
                            }
                    else:
                        msg = {
                            "topic": payload.topic,
                            "timestamp": payload.timestamp.isoformat(),
                            "payload": payload.payload_bytes.decode("utf-8", errors="replace"),
                        }
                    data_line = f"data: {json.dumps(msg)}\n\n".encode()
                    self.wfile.write(data_line)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            if self.sse_tracker:
                self.sse_tracker.release()

    def _send_problem(
        self,
        status_code: int,
        title: str,
        detail: str,
        instance: str,
        source: str = "memory-buffer",
        plane: str = "system",
    ) -> None:
        """Send RFC 7807 problem details error response with telemetry headers."""
        problem = {
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
        }
        body = json.dumps(problem).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/problem+json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Telemetry-Source", source)
        self.send_header("X-Telemetry-Plane", plane)
        self._apply_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(
        self,
        status_code: int,
        data: Any,
        source: str = "memory-buffer",
        plane: str = "system",
        etag: str | None = None,
    ) -> None:
        """Send JSON response with mandatory X-Telemetry-Source, X-Telemetry-Plane, and optional ETag."""
        if etag:
            if_none_match = self.headers.get("If-None-Match")
            if if_none_match and (if_none_match == etag or if_none_match == f'"{etag}"'):
                self.send_response(304)
                self.send_header("ETag", f'"{etag}"' if not etag.startswith('"') else etag)
                self.send_header("X-Telemetry-Source", source)
                self.send_header("X-Telemetry-Plane", plane)
                self._apply_cors_headers()
                self.end_headers()
                return

        def _default_encoder(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, bytes):
                return obj.decode("utf-8", errors="replace")
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        body = json.dumps(data, default=_default_encoder).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Telemetry-Source", source)
        self.send_header("X-Telemetry-Plane", plane)
        if etag:
            self.send_header("ETag", f'"{etag}"' if not etag.startswith('"') else etag)
        self._apply_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard stderr request spam."""
        pass


class HttpApiAdapter:
    """Driving adapter hosting a multi-threaded HTTP/SSE server."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        api_key: str | None = None,
        allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS,
        watcher_status_port: GetWatcherStatusPort | None = None,
        process_stream_port: ProcessTelemetryStreamPort | None = None,
        find_events_port: FindTelemetryEventsPort | None = None,
        get_events_port: GetTelemetryEventsPort | None = None,
        stream_events_port: GetTelemetryStreamPort | None = None,
        game_status_port: GetLatestGameStatusPort | None = None,
        journal_path_port: FindJournalPathPort | None = None,
        journal_files_port: GetJournalFilesPort | None = None,
        aux_snapshot_port: GetAuxiliarySnapshotPort | None = None,
        diagnostic_logs_port: GetDiagnosticLogsPort | None = None,
        telemetry_head_port: GetTelemetryHeadPort | None = None,
        telemetry_state_port: GetTelemetryStatePort | None = None,
        state_heartbeat_port: GetStateHeartbeatPort | None = None,
        max_sse_clients: int = 16,
        api_key_resolver: Callable[[], str | None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key
        self.api_key_resolver = api_key_resolver
        self.allowed_origins = allowed_origins
        self.max_sse_clients = max_sse_clients
        self.watcher_status_port = watcher_status_port
        self.process_stream_port = process_stream_port
        self.find_events_port = find_events_port
        self.get_events_port = get_events_port
        self.stream_events_port = stream_events_port
        self.game_status_port = game_status_port
        self.journal_path_port = journal_path_port
        self.journal_files_port = journal_files_port
        self.aux_snapshot_port = aux_snapshot_port
        self.diagnostic_logs_port = diagnostic_logs_port
        self.telemetry_head_port = telemetry_head_port
        self.telemetry_state_port = telemetry_state_port
        self.state_heartbeat_port = state_heartbeat_port

        self._sse_tracker = SSEConnectionTracker(max_clients=max_sse_clients)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background HTTP server."""
        # Determine active resolver: explicit resolver > DynamicCredentialProvider(static_override=self.api_key)
        active_resolver = self.api_key_resolver
        if active_resolver is None:
            active_resolver = DynamicCredentialProvider(static_override=self.api_key)

        handler_cls = type(
            "BoundTelemetryHttpHandler",
            (TelemetryHttpHandler,),
            {
                "watcher_status_port": self.watcher_status_port,
                "process_stream_port": self.process_stream_port,
                "find_events_port": self.find_events_port,
                "get_events_port": self.get_events_port,
                "stream_events_port": self.stream_events_port,
                "game_status_port": self.game_status_port,
                "journal_path_port": self.journal_path_port,
                "journal_files_port": self.journal_files_port,
                "aux_snapshot_port": self.aux_snapshot_port,
                "diagnostic_logs_port": self.diagnostic_logs_port,
                "telemetry_head_port": self.telemetry_head_port,
                "telemetry_state_port": self.telemetry_state_port,
                "state_heartbeat_port": self.state_heartbeat_port,
                "server_api_key": self.api_key,
                "api_key_resolver": active_resolver,
                "allowed_origins": self.allowed_origins,
                "sse_tracker": self._sse_tracker,
            },
        )

        self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        # Re-capture assigned port if ephemeral 0 was requested
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop and shutdown the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        """Check if server is active."""
        return self._server is not None
