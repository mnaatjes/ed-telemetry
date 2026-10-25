"""Driving adapter providing a zero-dependency HTTP and SSE server."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ed_telemetry.core.ports.driving.telemetry_port import (
    FindJournalPathPort,
    FindTelemetryEventsPort,
    GetAuxiliarySnapshotPort,
    GetDiagnosticLogsPort,
    GetJournalFilesPort,
    GetLatestGameStatusPort,
    GetTelemetryEventsPort,
    GetTelemetryStreamPort,
    GetWatcherStatusPort,
    ProcessTelemetryStreamPort,
    TelemetryQueryDTO,
)


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

    def do_GET(self) -> None:
        """Handle incoming GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        if path in ("", "/api/v1/health"):
            self._send_json(200, {"status": "ok", "service": "ed-telemetry"})
            return

        if path == "/api/v1/diagnostics/logs":
            if not self.diagnostic_logs_port:
                self._send_problem(
                    status_code=503,
                    title="Service Unavailable",
                    detail="Diagnostic log port is not configured.",
                    instance=path,
                )
                return
            min_level = query["min_level"][0] if "min_level" in query else None
            limit = int(query["limit"][0]) if "limit" in query else 100
            snapshot = self.diagnostic_logs_port.get_logs(min_level=min_level, limit=limit)
            self._send_json(200, asdict(snapshot))
            return

        if path == "/api/v1/status":
            status_dto = self.watcher_status_port.get_status()
            self._send_json(200, asdict(status_dto))
            return

        if path == "/api/v1/events":
            since_id = int(query["since_id"][0]) if "since_id" in query else None
            topic = query["topic"][0] if "topic" in query else None
            limit = int(query["limit"][0]) if "limit" in query else 100
            q_dto = TelemetryQueryDTO(since_id=since_id, topic=topic, limit=limit)
            records = self.find_events_port.find_events(q_dto)
            self._send_json(200, [asdict(r) for r in records])
            return

        if path == "/api/v1/events/buffer":
            limit = int(query["limit"][0]) if "limit" in query else 100
            batch = self.get_events_port.get_events(limit=limit)
            self._send_json(200, asdict(batch))
            return

        if path == "/api/v1/status/game":
            snap = self.game_status_port.get_game_status()
            self._send_json(200, asdict(snap))
            return

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
                )
                return

            if not aux_snap.exists:
                self._send_problem(
                    status_code=404,
                    title="Snapshot Not Found",
                    detail=f"Auxiliary game snapshot '{snapshot_name}' does not exist.",
                    instance=path,
                )
                return
            self._send_json(200, asdict(aux_snap))
            return

        if path == "/api/v1/stream":
            self._handle_sse_stream()
            return

        self._send_problem(
            status_code=404,
            title="Not Found",
            detail=f"Resource '{path}' does not exist on this server.",
            instance=path,
        )

    def do_POST(self) -> None:
        """Handle incoming POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/v1/control/watch":
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
                )
                return

            action = data.get("action", "start")
            if action == "start":
                self.process_stream_port.start_streaming()
                self._send_json(200, {"action": "start", "result": "started"})
            elif action == "stop":
                self.process_stream_port.stop_streaming()
                self._send_json(200, {"action": "stop", "result": "stopped"})
            else:
                self._send_problem(
                    status_code=400,
                    title="Bad Request",
                    detail=f"Unknown control action: '{action}'. Expected 'start' or 'stop'.",
                    instance=path,
                )
            return

        self._send_problem(
            status_code=404,
            title="Not Found",
            detail=f"Endpoint '{path}' does not accept POST requests.",
            instance=path,
        )

    def _handle_sse_stream(self) -> None:
        """Serve Server-Sent Events (SSE) live feed."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send initial connected heartbeat
        self.wfile.write(b'data: {"event":"connected"}\n\n')
        self.wfile.flush()

        try:
            for payload in self.stream_events_port.stream_events(timeout=0.5):
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

    def _send_problem(self, status_code: int, title: str, detail: str, instance: str) -> None:
        """Send RFC 7807 problem details error response."""
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status_code: int, data: Any) -> None:
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
        self.send_header("Access-Control-Allow-Origin", "*")
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
    ) -> None:
        self.host = host
        self.port = port
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

        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background HTTP server."""
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
