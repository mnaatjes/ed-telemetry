"""CLI driving adapter for operational command execution and telemetry inspection."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any

from ed_telemetry.core.ports.driving.telemetry_port import (
    FindTelemetryEventsPort,
    GetDiagnosticLogsPort,
    GetLatestGameStatusPort,
    GetTelemetryStreamPort,
    GetWatcherStatusPort,
    ProcessTelemetryStreamPort,
    TelemetryQueryDTO,
)


def _json_serial(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class CliTelemetryAdapter:
    """Driving adapter executing terminal CLI commands mapped to application use cases."""

    def __init__(
        self,
        watcher_status_port: GetWatcherStatusPort,
        game_status_port: GetLatestGameStatusPort,
        find_events_port: FindTelemetryEventsPort,
        process_stream_port: ProcessTelemetryStreamPort,
        http_api_adapter: Any,
        diagnostic_logs_port: GetDiagnosticLogsPort | None = None,
        stream_events_port: GetTelemetryStreamPort | None = None,
    ) -> None:
        self._watcher_status_port = watcher_status_port
        self._game_status_port = game_status_port
        self._find_events_port = find_events_port
        self._process_stream_port = process_stream_port
        self._http_api_adapter = http_api_adapter
        self._diagnostic_logs_port = diagnostic_logs_port
        self._stream_events_port = stream_events_port

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="ed-telemetry",
            description="Elite Dangerous Telemetry Daemon and Inspection Tool",
        )
        subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

        # Subcommand: status
        status_parser = subparsers.add_parser("status", help="Query watcher or game status")
        status_parser.add_argument(
            "target",
            nargs="?",
            choices=["game"],
            help="Optional target to inspect ('game' for player cockpit status)",
        )
        status_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: serve
        serve_parser = subparsers.add_parser("serve", help="Run background telemetry daemon and HTTP API")
        serve_parser.add_argument("--host", default="127.0.0.1", help="HTTP server host (default: 127.0.0.1)")
        serve_parser.add_argument("--port", type=int, default=8080, help="HTTP server port (default: 8080)")
        serve_parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Application logging verbosity level",
        )
        serve_parser.add_argument("--log-file", help="Path to write rotating application log file")

        # Subcommand: events
        events_parser = subparsers.add_parser("events", help="Query stored historical events from SQLite")
        events_parser.add_argument("--topic", help="Filter by topic (e.g. telemetry.journal)")
        events_parser.add_argument("--since-id", type=int, help="Filter records newer than given ID")
        events_parser.add_argument("--limit", type=int, default=20, help="Maximum events to return (default: 20)")
        events_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: logs
        logs_parser = subparsers.add_parser("logs", help="Inspect in-memory diagnostic application logs")
        logs_parser.add_argument(
            "--level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Minimum log severity level to display",
        )
        logs_parser.add_argument("--limit", type=int, default=50, help="Maximum log records to return (default: 50)")
        logs_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: tail
        tail_parser = subparsers.add_parser("tail", help="Follow live telemetry and audit SSE stream")
        tail_parser.add_argument(
            "--topic",
            help="Optional topic filter (e.g. telemetry.audit or telemetry.journal)",
        )
        tail_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        return parser

    def run(self, argv: Sequence[str] | None = None) -> tuple[int, dict[str, Any]]:
        """Parse arguments and dispatch command. Returns POSIX exit code and output payload."""
        parser = self._build_parser()
        args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])

        if args.subcommand is None or args.subcommand == "status":
            return self._handle_status(args)

        if args.subcommand == "serve":
            return self._handle_serve(args)

        if args.subcommand == "events":
            return self._handle_events(args)

        if args.subcommand == "logs":
            return self._handle_logs(args)

        if args.subcommand == "tail":
            return self._handle_tail(args)

        parser.print_help()
        return 0, {}

    def _handle_status(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        target = getattr(args, "target", None)
        as_json = getattr(args, "json", False)

        if target == "game":
            game_status = self._game_status_port.get_game_status()
            payload = asdict(game_status)
            if as_json:
                print(json.dumps(payload, default=_json_serial, indent=2))
            else:
                exists_str = "Found" if game_status.exists else "Not Found"
                print(f"Game Status Snapshot: {exists_str}")
                if game_status.target_path:
                    print(f"Path: {game_status.target_path}")
                if game_status.timestamp:
                    print(f"Timestamp: {game_status.timestamp.isoformat()}")
            return 0, payload

        watcher_status = self._watcher_status_port.get_status()
        payload = asdict(watcher_status)
        if as_json:
            print(json.dumps(payload, default=_json_serial, indent=2))
        else:
            state_str = "Active" if watcher_status.is_active else "Idle"
            print(f"Watcher State: {state_str}")
            print(f"Monitored Directory: {watcher_status.monitored_directory or 'None'}")
            print(f"Active Journal: {watcher_status.active_journal or 'None'}")
        return 0, payload

    def _handle_events(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        query = TelemetryQueryDTO(
            since_id=args.since_id,
            topic=args.topic,
            limit=args.limit,
        )
        records = self._find_events_port.find_events(query)
        payload = {"records": [asdict(r) for r in records], "count": len(records)}

        if args.json:
            print(json.dumps(payload, default=_json_serial, indent=2))
        else:
            print(f"Retrieved {len(records)} events:")
            for r in records:
                print(f"[{r.id}] {r.timestamp.isoformat()} ({r.topic}): {r.payload_json[:80]}")
        return 0, payload

    def _handle_serve(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        self._http_api_adapter.host = args.host
        self._http_api_adapter.port = args.port

        print(f"Starting ed-telemetry daemon on {args.host}:{args.port}...")
        self._process_stream_port.start_streaming()
        self._http_api_adapter.start()
        print(f"HTTP/SSE API listening on http://{args.host}:{self._http_api_adapter.port}/api/v1")
        print("Press Ctrl+C to stop.")

        try:
            while self._http_api_adapter.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nShutting down ed-telemetry...")
        finally:
            self._http_api_adapter.stop()
            self._process_stream_port.stop_streaming()
            print("Stopped cleanly.")

        return 0, {"status": "stopped"}

    def _handle_logs(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        if not self._diagnostic_logs_port:
            print("Diagnostic logging port is not configured.")
            return 1, {"error": "Diagnostic logging port not configured"}

        level = getattr(args, "level", None)
        limit = getattr(args, "limit", 50)
        as_json = getattr(args, "json", False)

        snapshot = self._diagnostic_logs_port.get_logs(min_level=level, limit=limit)
        payload = asdict(snapshot)

        if as_json:
            print(json.dumps(payload, default=_json_serial, indent=2))
        else:
            print(f"Diagnostic Logs ({len(snapshot.records)} records):")
            for r in snapshot.records:
                ts = r.timestamp.isoformat()
                print(f"[{ts}] [{r.level:<5}] {r.logger_name}: {r.message}")
        return 0, payload

    def _handle_tail(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        if not self._stream_events_port:
            print("Telemetry stream port is not configured.")
            return 1, {"error": "Telemetry stream port not configured"}

        topic_filter = getattr(args, "topic", None)
        as_json = getattr(args, "json", False)

        filter_desc = f" (filter: {topic_filter})" if topic_filter else ""
        print(f"Streaming live telemetry{filter_desc}... Press Ctrl+C to stop.")

        count = 0
        try:
            for payload in self._stream_events_port.stream_events(timeout=0.5):
                if topic_filter and payload.topic != topic_filter:
                    continue
                count += 1
                msg = {
                    "topic": payload.topic,
                    "timestamp": payload.timestamp.isoformat(),
                    "payload": payload.payload_bytes.decode("utf-8", errors="replace"),
                }
                if as_json:
                    print(json.dumps(msg))
                else:
                    print(f"[{msg['timestamp']}] ({msg['topic']}): {msg['payload']}")
        except KeyboardInterrupt:
            print("\nStopped streaming.")

        return 0, {"streamed": count}
