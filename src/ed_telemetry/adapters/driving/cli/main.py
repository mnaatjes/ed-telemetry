"""CLI driving adapter for operational command execution and telemetry inspection."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any

from ed_telemetry.adapters.driven.watcher.discovery.exceptions import PathDiscoveryError
from ed_telemetry.core.ports.driving.telemetry_port import (
    FindJournalPathPort,
    FindTelemetryEventsPort,
    GetDiagnosticLogsPort,
    GetJournalFilesPort,
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


def _probe_daemon(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """Probe running daemon health endpoint to determine online availability."""
    url = f"http://{host}:{port}/api/v1/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.2) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


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
        journal_path_port: FindJournalPathPort | None = None,
        journal_files_port: GetJournalFilesPort | None = None,
    ) -> None:
        self._watcher_status_port = watcher_status_port
        self._game_status_port = game_status_port
        self._find_events_port = find_events_port
        self._process_stream_port = process_stream_port
        self._http_api_adapter = http_api_adapter
        self._diagnostic_logs_port = diagnostic_logs_port
        self._stream_events_port = stream_events_port
        self._journal_path_port = journal_path_port
        self._journal_files_port = journal_files_port

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
        serve_parser.add_argument(
            "--host",
            default=os.environ.get("ED_HTTP_HOST", "127.0.0.1"),
            help="HTTP server host (default: 127.0.0.1 or $ED_HTTP_HOST)",
        )
        serve_parser.add_argument(
            "--port",
            type=int,
            default=int(os.environ["ED_HTTP_PORT"]) if "ED_HTTP_PORT" in os.environ else 8080,
            help="HTTP server port (default: 8080 or $ED_HTTP_PORT)",
        )
        serve_parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default=os.environ.get("ED_LOG_LEVEL", "INFO"),
            help="Application logging verbosity level (default: INFO or $ED_LOG_LEVEL)",
        )
        serve_parser.add_argument(
            "--log-file",
            default=os.environ.get("ED_LOG_FILE"),
            help="Path to write rotating application log file (default: OS default or $ED_LOG_FILE)",
        )
        serve_parser.add_argument(
            "--journal-dir",
            default=os.environ.get("ED_JOURNAL_DIR"),
            help="Explicit path to journal directory (default: auto-discovered or $ED_JOURNAL_DIR)",
        )
        serve_parser.add_argument(
            "--db-path",
            default=os.environ.get("ED_DB_PATH"),
            help="Path to SQLite database file (default: OS default or $ED_DB_PATH)",
        )
        serve_parser.add_argument(
            "--poll-interval",
            type=float,
            default=float(os.environ["ED_POLL_INTERVAL"]) if "ED_POLL_INTERVAL" in os.environ else None,
            help="Watcher polling interval in seconds (default: OS default or $ED_POLL_INTERVAL)",
        )

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

        host = getattr(self._http_api_adapter, "host", "127.0.0.1")
        port = getattr(self._http_api_adapter, "port", 8080)
        is_online = _probe_daemon(host, port)

        if target == "game":
            if is_online:
                try:
                    url = f"http://{host}:{port}/api/v1/status/game"
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                        if as_json:
                            print(json.dumps(payload, default=_json_serial, indent=2))
                        else:
                            exists_str = "Found" if payload.get("exists") else "Not Found"
                            print(f"Game Status Snapshot: {exists_str}")
                            if payload.get("target_path"):
                                print(f"Path: {payload['target_path']}")
                            if payload.get("timestamp"):
                                print(f"Timestamp: {payload['timestamp']}")
                        return 0, payload
                except Exception:
                    pass

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

        # Watcher status
        if is_online:
            try:
                url = f"http://{host}:{port}/api/v1/status"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if as_json:
                        print(json.dumps(payload, default=_json_serial, indent=2))
                    else:
                        state_str = "Active" if payload.get("is_active") else "Idle"
                        print(f"Watcher State: {state_str}")
                        monitored = payload.get("monitored_directory")
                        if monitored:
                            print(f"Monitored Directory: {monitored}")
                        else:
                            print("Monitored Directory: Not Found (Use --journal-dir or $ED_JOURNAL_DIR)")
                        print(f"Active Journal: {payload.get('active_journal') or 'None'}")
                    return 0, payload
            except Exception:
                pass

        watcher_status = self._watcher_status_port.get_status()
        payload = asdict(watcher_status)
        if watcher_status.monitored_directory is None:
            payload["discovery_error"] = "No valid journal directory detected"

        if as_json:
            print(json.dumps(payload, default=_json_serial, indent=2))
        else:
            state_str = "Active" if watcher_status.is_active else "Idle"
            print(f"Watcher State: {state_str}")
            if watcher_status.monitored_directory:
                print(f"Monitored Directory: {watcher_status.monitored_directory}")
            else:
                print("Monitored Directory: Not Found (Use --journal-dir or $ED_JOURNAL_DIR)")
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

        discovered_path = None
        discovery_source = "Unknown"
        override = args.journal_dir

        if self._journal_path_port:
            try:
                path_dto = self._journal_path_port.find_path(override_path=override)
                discovered_path = path_dto.resolved_path
                discovery_source = path_dto.discovery_source
            except (PathDiscoveryError, Exception) as err:
                sys.stderr.write("[ERROR] Failed to discover Elite Dangerous journal directory.\n")
                sys.stderr.write(
                    "Evaluated strategies: Windows Registry, Steam Proton (AppID 359320), Default User Paths.\n"
                )
                sys.stderr.write("Remediation:\n")
                sys.stderr.write(
                    '  1. Pass the path explicitly: ed-telemetry serve --journal-dir "/path/to/journal/folder"\n'
                )
                sys.stderr.write('  2. Or set environment variable: export ED_JOURNAL_DIR="/path/to/journal/folder"\n')
                return 1, {"error": str(err)}

        active_journal_name = None
        if self._journal_files_port:
            try:
                files_dto = self._journal_files_port.get_journals()
                active_journal_name = files_dto.active_journal
            except Exception:
                pass

        print(f"Starting ed-telemetry daemon on {args.host}:{args.port}...")
        if discovered_path:
            print(f"Discovered Journal Directory: {discovered_path} (Source: {discovery_source})")
        if active_journal_name:
            print(f"Active Journal: {active_journal_name}")
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
        level = getattr(args, "level", None)
        limit = getattr(args, "limit", 50)
        as_json = getattr(args, "json", False)

        host = getattr(self._http_api_adapter, "host", "127.0.0.1")
        port = getattr(self._http_api_adapter, "port", 8080)

        if _probe_daemon(host, port):
            try:
                params = [f"limit={limit}"]
                if level:
                    params.append(f"min_level={level}")
                query_str = "&".join(params)
                url = f"http://{host}:{port}/api/v1/diagnostics/logs?{query_str}"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if as_json:
                        print(json.dumps(payload, default=_json_serial, indent=2))
                    else:
                        records = payload.get("records", [])
                        print(f"Diagnostic Logs ({len(records)} records):")
                        for r in records:
                            lvl = r.get("level", "")
                            print(f"[{r.get('timestamp')}] [{lvl:<5}] {r.get('logger_name')}: {r.get('message')}")
                    return 0, payload
            except Exception:
                pass

        # Offline fallback: read rotating log file from resolve_default_log_path()
        from ed_telemetry.adapters.paths import resolve_default_log_path

        log_file_path = resolve_default_log_path()
        records_list: list[dict[str, Any]] = []
        if log_file_path.exists():
            log_line_regex = re.compile(
                r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+\[(?P<level>[A-Z]+)\]\s+(?P<name>[^:]+):\s+(?P<msg>.*)$"
            )
            level_ranks = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
            min_rank = level_ranks.get(level.upper(), 0) if level else 0

            with open(log_file_path, encoding="utf-8", errors="replace") as fp:
                lines = fp.readlines()
                for line in reversed(lines):
                    m = log_line_regex.match(line.strip())
                    if m:
                        rec_level = m.group("level")
                        if level_ranks.get(rec_level, 0) >= min_rank:
                            records_list.append(
                                {
                                    "timestamp": m.group("ts"),
                                    "level": rec_level,
                                    "logger_name": m.group("name"),
                                    "message": m.group("msg"),
                                }
                            )
                            if len(records_list) >= limit:
                                break
            records_list.reverse()

            payload = {
                "records": records_list,
                "total_retained": len(records_list),
                "capacity": limit,
            }

            if as_json:
                print(json.dumps(payload, default=_json_serial, indent=2))
            else:
                print(f"Diagnostic Logs ({len(records_list)} records):")
                for r in records_list:
                    print(f"[{r['timestamp']}] [{r['level']:<5}] {r['logger_name']}: {r['message']}")
            return 0, payload

        # Fallback to in-memory port if no log file
        if self._diagnostic_logs_port:
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

        return 0, {"records": [], "total_retained": 0, "capacity": limit}

    def _handle_tail(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        topic_filter = getattr(args, "topic", None)
        as_json = getattr(args, "json", False)

        host = getattr(self._http_api_adapter, "host", "127.0.0.1")
        port = getattr(self._http_api_adapter, "port", 8080)

        filter_desc = f" (filter: {topic_filter})" if topic_filter else ""
        print(f"Streaming live telemetry{filter_desc}... Press Ctrl+C to stop.")

        count = 0
        if _probe_daemon(host, port):
            try:
                url = f"http://{host}:{port}/api/v1/stream"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=None) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if line.startswith("data: "):
                            raw_data = line[6:]
                            try:
                                msg = json.loads(raw_data)
                                if msg.get("event") == "connected":
                                    continue
                                if topic_filter and msg.get("topic") != topic_filter:
                                    continue
                                count += 1
                                if as_json:
                                    print(json.dumps(msg))
                                else:
                                    print(f"[{msg.get('timestamp')}] ({msg.get('topic')}): {msg.get('payload')}")
                            except json.JSONDecodeError:
                                pass
            except (KeyboardInterrupt, urllib.error.URLError, OSError):
                print("\nStopped streaming.")
            return 0, {"streamed": count}

        # Offline standalone fallback
        if not self._stream_events_port or not self._process_stream_port:
            print("Telemetry stream port is not configured.")
            return 1, {"error": "Telemetry stream port not configured"}

        self._process_stream_port.start_streaming()
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
        finally:
            self._process_stream_port.stop_streaming()

        return 0, {"streamed": count}
