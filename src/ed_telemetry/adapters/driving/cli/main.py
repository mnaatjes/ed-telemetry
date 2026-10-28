"""CLI driving adapter for operational command execution and telemetry inspection."""

from __future__ import annotations

import argparse
import errno
import ipaddress
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ed_telemetry import __version__
from ed_telemetry.adapters.driven.watcher.discovery.exceptions import PathDiscoveryError
from ed_telemetry.adapters.paths import (
    resolve_default_credentials_path,
    sanitize_host_path,
)
from ed_telemetry.core.ports.driving.telemetry_port import (
    FindJournalPathPort,
    FindTelemetryEventsPort,
    GetDatabaseStatsPort,
    GetDiagnosticLogsPort,
    GetJournalFilesPort,
    GetLatestGameStatusPort,
    GetTelemetryStreamPort,
    GetWatcherStatusPort,
    MaintainDatabasePort,
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


def _build_authenticated_request(url: str, api_key: str | None = None) -> urllib.request.Request:
    """Build an HTTP Request with optional Bearer Authorization header."""
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return urllib.request.Request(url, headers=headers, method="GET")


def is_loopback_host(host: str) -> bool:
    """Determine whether a host string represents a loopback interface."""
    host_clean = host.strip().lower()
    if host_clean in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        ip = ipaddress.ip_address(host_clean)
        return ip.is_loopback
    except ValueError:
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
        database_stats_port: GetDatabaseStatsPort | None = None,
        maintain_database_port: MaintainDatabasePort | None = None,
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
        self._database_stats_port = database_stats_port
        self._maintain_database_port = maintain_database_port

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="ed-telemetry",
            description="Elite Dangerous Telemetry Daemon and Inspection Tool",
        )
        parser.add_argument(
            "-v",
            "--version",
            action="version",
            version=f"%(prog)s {__version__}",
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
            "--api-key",
            default=None,
            help="Pre-shared API key for authentication (default: resolved from env or credentials.json)",
        )
        serve_parser.add_argument(
            "--allow-insecure",
            action="store_true",
            help="Explicitly permit unauthenticated access on non-loopback network interfaces",
        )
        serve_parser.add_argument(
            "--allowed-origin",
            action="append",
            dest="allowed_origins",
            help="Additional allowed CORS origin (can be specified multiple times)",
        )
        serve_parser.add_argument(
            "--poll-interval",
            type=float,
            default=float(os.environ["ED_POLL_INTERVAL"]) if "ED_POLL_INTERVAL" in os.environ else None,
            help="Watcher polling interval in seconds (default: OS default or $ED_POLL_INTERVAL)",
        )
        serve_parser.add_argument(
            "--retention-days",
            type=int,
            default=int(os.environ["ED_DB_RETENTION_DAYS"]) if "ED_DB_RETENTION_DAYS" in os.environ else None,
            help="Optional max event retention in days (default: unlimited or $ED_DB_RETENTION_DAYS)",
        )
        serve_parser.add_argument(
            "--retention-max-records",
            type=int,
            default=int(os.environ["ED_DB_MAX_RECORDS"]) if "ED_DB_MAX_RECORDS" in os.environ else None,
            help="Optional maximum number of records to retain (default: unlimited or $ED_DB_MAX_RECORDS)",
        )

        # Subcommand: db
        db_parser = subparsers.add_parser("db", help="Manage SQLite persistence database, stats, and retention")
        db_subparsers = db_parser.add_subparsers(dest="db_action", help="Database actions")

        # db status
        db_status_parser = db_subparsers.add_parser("status", help="Inspect database size, record counts, and bounds")
        db_status_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # db prune
        db_prune_parser = db_subparsers.add_parser("prune", help="Prune historical events by age or record ceiling")
        db_prune_parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Prune records older than specified number of days",
        )
        db_prune_parser.add_argument(
            "--max-records",
            type=int,
            default=None,
            help="Retain at most specified number of newest records (FIFO pruning)",
        )
        db_prune_parser.add_argument(
            "--vacuum",
            action="store_true",
            help="Run SQLite VACUUM after pruning to reclaim disk space",
        )
        db_prune_parser.add_argument(
            "--force",
            action="store_true",
            help="Bypass confirmation prompt",
        )
        db_prune_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # db vacuum
        db_vacuum_parser = db_subparsers.add_parser("vacuum", help="Reclaim fragmented disk space via SQLite VACUUM")
        db_vacuum_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: auth
        auth_parser = subparsers.add_parser("auth", help="Manage pre-shared API keys and environment credentials")
        auth_subparsers = auth_parser.add_subparsers(dest="auth_action", help="Auth actions")

        # auth keygen
        keygen_parser = auth_subparsers.add_parser("keygen", help="Generate and store a new CSPRNG API key")
        keygen_parser.add_argument(
            "--force", action="store_true", help="Overwrite existing credentials file if present"
        )
        keygen_parser.add_argument(
            "--register-env",
            action="store_true",
            help="Automatically register key in user environment (~/.bashrc / ~/.zshrc or Windows user env)",
        )
        keygen_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # auth show
        show_parser = auth_subparsers.add_parser("show", help="Display currently resolved API key and source")
        show_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # auth revoke
        revoke_parser = auth_subparsers.add_parser(
            "revoke", help="Remove credentials file and registered environment variables"
        )
        revoke_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: events
        events_parser = subparsers.add_parser("events", help="Query stored historical events from SQLite")
        events_parser.add_argument("--topic", help="Filter by topic (e.g. telemetry.journal)")
        events_parser.add_argument("--since-id", type=int, help="Filter records newer than given ID")
        events_parser.add_argument("--limit", type=int, default=20, help="Maximum events to return (default: 20)")
        events_parser.add_argument("-f", "--follow", action="store_true", help="Continuously stream new events")
        events_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: logs
        logs_parser = subparsers.add_parser("logs", help="Inspect diagnostic application logs")
        logs_parser.add_argument(
            "--level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Minimum log severity level to display",
        )
        logs_parser.add_argument("--limit", type=int, default=50, help="Maximum log records to return (default: 50)")
        logs_parser.add_argument("-f", "--follow", action="store_true", help="Continuously follow rotating disk logs")
        logs_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: stream (Canonical command for live SSE event bus)
        stream_parser = subparsers.add_parser("stream", help="Follow live telemetry and audit SSE stream")
        stream_parser.add_argument(
            "--topic",
            help="Optional topic filter (e.g. telemetry.audit or telemetry.journal)",
        )
        stream_parser.add_argument(
            "--api-key",
            default=None,
            help="Pre-shared API key for authentication (default: resolved from env or credentials.json)",
        )
        stream_parser.add_argument("--json", action="store_true", help="Format output as JSON")

        # Subcommand: tail (Backwards-compatible alias for stream)
        tail_parser = subparsers.add_parser("tail", help="Alias for 'stream' (follow live telemetry stream)")
        tail_parser.add_argument(
            "--topic",
            help="Optional topic filter (e.g. telemetry.audit or telemetry.journal)",
        )
        tail_parser.add_argument(
            "--api-key",
            default=None,
            help="Pre-shared API key for authentication (default: resolved from env or credentials.json)",
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
            if getattr(args, "follow", False):
                return self._handle_stream(args)
            return self._handle_events(args)

        if args.subcommand == "logs":
            return self._handle_logs(args)

        if args.subcommand == "auth":
            return self._handle_auth(args)

        if args.subcommand == "db":
            return self._handle_db(args)

        if args.subcommand in ("stream", "tail"):
            return self._handle_stream(args)

        parser.print_help()
        return 0, {}

    def _handle_status(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        target = getattr(args, "target", None)
        as_json = getattr(args, "json", False)

        host = getattr(self._http_api_adapter, "host", "127.0.0.1")
        port = getattr(self._http_api_adapter, "port", 8080)
        is_online = _probe_daemon(host, port)

        api_key = self._resolve_api_key(getattr(args, "api_key", None))
        if target == "game":
            if is_online:
                try:
                    url = f"http://{host}:{port}/api/v1/status/game"
                    req = _build_authenticated_request(url, api_key=api_key)
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                        if payload.get("target_path"):
                            payload["target_path"] = sanitize_host_path(payload["target_path"])
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
            if payload.get("target_path"):
                payload["target_path"] = sanitize_host_path(payload["target_path"])
            if as_json:
                print(json.dumps(payload, default=_json_serial, indent=2))
            else:
                exists_str = "Found" if game_status.exists else "Not Found"
                print(f"Game Status Snapshot: {exists_str}")
                if payload.get("target_path"):
                    print(f"Path: {payload['target_path']}")
                if game_status.timestamp:
                    print(f"Timestamp: {game_status.timestamp.isoformat()}")
            return 0, payload

        # Watcher status
        if is_online:
            try:
                url = f"http://{host}:{port}/api/v1/status"
                req = _build_authenticated_request(url, api_key=api_key)
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if payload.get("monitored_directory"):
                        payload["monitored_directory"] = sanitize_host_path(payload["monitored_directory"])
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
        if payload.get("monitored_directory"):
            payload["monitored_directory"] = sanitize_host_path(payload["monitored_directory"])
        if watcher_status.monitored_directory is None:
            payload["discovery_error"] = "No valid journal directory detected"

        if as_json:
            print(json.dumps(payload, default=_json_serial, indent=2))
        else:
            state_str = "Active" if watcher_status.is_active else "Idle"
            print(f"Watcher State: {state_str}")
            if payload.get("monitored_directory"):
                print(f"Monitored Directory: {payload['monitored_directory']}")
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

        # If explicit CLI flag was passed, pin that key; otherwise use dynamic provider for hot-reloading
        cli_override = getattr(args, "api_key", None)
        resolved_key = self._resolve_api_key(cli_override)
        if cli_override:
            self._http_api_adapter.api_key = cli_override.strip()
            self._http_api_adapter.api_key_resolver = None
        else:
            self._http_api_adapter.api_key = None
            from ed_telemetry.adapters.driving.api.server import DynamicCredentialProvider

            self._http_api_adapter.api_key_resolver = DynamicCredentialProvider(
                credentials_path=resolve_default_credentials_path()
            )
        if getattr(args, "allowed_origins", None):
            self._http_api_adapter.allowed_origins = tuple(args.allowed_origins)

        # Non-loopback security gate (ADR 0032 / SDD-030)
        is_loopback = is_loopback_host(args.host)
        allow_insecure = getattr(args, "allow_insecure", False)

        if not is_loopback and not resolved_key and not allow_insecure:
            sys.stderr.write(
                f"[SECURITY ERROR] Refusing to bind to non-loopback host '{args.host}' without authentication.\n"
                "All telemetry streams and endpoints would be accessible unauthenticated to network peers.\n\n"
                "Remediation:\n"
                "  1. Generate and register an API key: ed-telemetry auth keygen --register-env\n"
                f"  2. Or pass an API key directly:      ed-telemetry serve --host {args.host} --api-key <TOKEN>\n"
                f"  3. Or explicitly permit insecure:    ed-telemetry serve --host {args.host} --allow-insecure\n"
            )
            return 1, {
                "error": "Refusing to bind to non-loopback interface without authentication",
                "host": args.host,
            }

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
        if resolved_key:
            print("Perimeter Authentication: ENABLED (Pre-shared API key active)")
        elif is_loopback:
            print("Perimeter Authentication: DISABLED (Local loopback unauthenticated mode)")
        else:
            print("[WARNING] SECURITY RISK: Running on non-loopback host in unauthenticated mode.")
            print("          All telemetry endpoints are openly accessible to network peers.")
        if discovered_path:
            print(f"Discovered Journal Directory: {discovered_path} (Source: {discovery_source})")
        if active_journal_name:
            print(f"Active Journal: {active_journal_name}")
        self._process_stream_port.start_streaming()
        try:
            self._http_api_adapter.start()
        except OSError as err:
            self._process_stream_port.stop_streaming()
            if err.errno == errno.EADDRINUSE:
                sys.stderr.write(f"\n[ERROR] Port {args.port} is already in use by another process.\n")
                sys.stderr.write("Remediation:\n")
                sys.stderr.write('  1. Stop existing process:      pkill -f "ed-telemetry serve"\n')
                sys.stderr.write(
                    f"  2. Or specify a different port: ed-telemetry serve --port {args.port + 1} (or custom)\n"
                )
                return 1, {
                    "error": "Address already in use",
                    "host": args.host,
                    "port": args.port,
                }
            raise

        # Execute optional startup retention maintenance (ADR 0034)
        retention_days = getattr(args, "retention_days", None)
        max_records = getattr(args, "retention_max_records", None)
        if (retention_days or max_records) and self._maintain_database_port:
            try:
                res = self._maintain_database_port.maintain(
                    retention_days=retention_days,
                    max_records=max_records,
                    run_vacuum=False,
                )
                if res.pruned_count > 0:
                    print(f"Database Retention: Pruned {res.pruned_count} historical records.")
            except Exception as err:
                logging.warning("Failed to execute startup database retention: %s", err)

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
            if (retention_days or max_records) and self._maintain_database_port:
                try:
                    self._maintain_database_port.maintain(
                        retention_days=retention_days,
                        max_records=max_records,
                        run_vacuum=False,
                    )
                except Exception:
                    pass
            print("Stopped cleanly.")

        return 0, {"status": "stopped"}

    def _handle_logs(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        level = getattr(args, "level", None)
        limit = getattr(args, "limit", 50)
        as_json = getattr(args, "json", False)

        host = getattr(self._http_api_adapter, "host", "127.0.0.1")
        port = getattr(self._http_api_adapter, "port", 8080)

        follow = getattr(args, "follow", False)
        from ed_telemetry.adapters.paths import resolve_default_log_path

        log_file_path = resolve_default_log_path()

        if follow:
            return self._tail_disk_logs(log_file_path, level=level, as_json=as_json)

        if _probe_daemon(host, port):
            try:
                api_key = self._resolve_api_key(getattr(args, "api_key", None))
                params = [f"limit={limit}"]
                if level:
                    params.append(f"min_level={level}")
                query_str = "&".join(params)
                url = f"http://{host}:{port}/api/v1/diagnostics/logs?{query_str}"
                req = _build_authenticated_request(url, api_key=api_key)
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

    def _tail_disk_logs(self, log_path: Path, level: str | None, as_json: bool) -> tuple[int, dict[str, Any]]:
        """Follow rotating disk log file continuously (tail -f behavior)."""
        print(f"Following diagnostic logs from {log_path}... Press Ctrl+C to stop.")
        log_line_regex = re.compile(
            r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+\[(?P<level>[A-Z]+)\]\s+(?P<name>[^:]+):\s+(?P<msg>.*)$"
        )
        level_ranks = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
        min_rank = level_ranks.get(level.upper(), 0) if level else 0

        count = 0
        try:
            while not log_path.exists():
                time.sleep(0.5)

            with open(log_path, encoding="utf-8", errors="replace") as fp:
                # Seek to end of existing file
                fp.seek(0, 2)
                while True:
                    line = fp.readline()
                    if not line:
                        time.sleep(0.2)
                        continue
                    m = log_line_regex.match(line.strip())
                    if m:
                        rec_level = m.group("level")
                        if level_ranks.get(rec_level, 0) >= min_rank:
                            count += 1
                            item = {
                                "timestamp": m.group("ts"),
                                "level": rec_level,
                                "logger_name": m.group("name"),
                                "message": m.group("msg"),
                            }
                            if as_json:
                                print(json.dumps(item))
                            else:
                                lvl = item["level"]
                                msg_str = item["message"]
                                print(f"[{item['timestamp']}] [{lvl:<5}] {item['logger_name']}: {msg_str}")
        except KeyboardInterrupt:
            print("\nStopped log following.")

        return 0, {"followed": count}

    def _handle_stream(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        topic_filter = getattr(args, "topic", None)
        as_json = getattr(args, "json", False)

        host = getattr(self._http_api_adapter, "host", "127.0.0.1")
        port = getattr(self._http_api_adapter, "port", 8080)

        filter_desc = f" (filter: {topic_filter})" if topic_filter else ""
        print(f"Streaming live telemetry{filter_desc}... Press Ctrl+C to stop.")

        count = 0
        if _probe_daemon(host, port):
            try:
                api_key = self._resolve_api_key(getattr(args, "api_key", None))
                url = f"http://{host}:{port}/api/v1/stream"
                req = _build_authenticated_request(url, api_key=api_key)
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
            except KeyboardInterrupt:
                print("\nStopped streaming.")
                return 0, {"streamed": count}
            except urllib.error.HTTPError as err:
                err_detail = err.read().decode("utf-8", errors="replace")
                sys.stderr.write(f"\n[ERROR] Daemon returned HTTP {err.code} {err.reason}: {err_detail}\n")
                return 1, {"error": f"HTTP {err.code}", "detail": str(err.reason)}
            except (urllib.error.URLError, OSError) as err:
                sys.stderr.write(f"\n[ERROR] Network error while streaming: {err}\n")
                return 1, {"error": str(err)}
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

    def _resolve_api_key(self, cli_override: str | None = None) -> str | None:
        """Resolve API key using deterministic precedence: CLI flag -> ED_API_KEY -> credentials.json."""
        if cli_override:
            return cli_override.strip()

        env_key = os.environ.get("ED_API_KEY")
        if env_key:
            return env_key.strip()

        creds_path = resolve_default_credentials_path()
        if creds_path.exists():
            try:
                with open(creds_path, encoding="utf-8") as fp:
                    data = json.load(fp)
                    token = data.get("api_key")
                    if token and isinstance(token, str):
                        return token.strip()
            except (json.JSONDecodeError, OSError):
                pass

        return None

    def _handle_auth(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        action = getattr(args, "auth_action", None)
        as_json = getattr(args, "json", False)

        if action == "keygen":
            return self._handle_auth_keygen(args, as_json=as_json)
        if action == "show":
            return self._handle_auth_show(args, as_json=as_json)
        if action == "revoke":
            return self._handle_auth_revoke(args, as_json=as_json)

        print("Usage: ed-telemetry auth {keygen,show,revoke} [options]")
        return 0, {}

    def _handle_auth_keygen(self, args: argparse.Namespace, as_json: bool = False) -> tuple[int, dict[str, Any]]:
        creds_path = resolve_default_credentials_path()
        force = getattr(args, "force", False)
        register_env = getattr(args, "register_env", False)

        if creds_path.exists() and not force:
            err_msg = f"Credentials file already exists at {creds_path}. Use --force to overwrite."
            if as_json:
                print(json.dumps({"error": err_msg, "path": str(creds_path)}))
            else:
                sys.stderr.write(f"[ERROR] {err_msg}\n")
            return 1, {"error": err_msg}

        # Generate CSPRNG token: ed_sec_ + 48 hex chars (24 bytes entropy = 192 bits)
        token = f"ed_sec_{secrets.token_hex(24)}"
        creds_data = {
            "api_key": token,
            "created_at": datetime.now().isoformat(),
        }

        # Ensure parent dir exists with 0700 permissions
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            try:
                os.chmod(creds_path.parent, 0o700)
            except OSError:
                pass

        # Write file with 0600 permissions
        with open(creds_path, "w", encoding="utf-8") as fp:
            json.dump(creds_data, fp, indent=2)

        if os.name == "posix":
            try:
                os.chmod(creds_path, 0o600)
            except OSError:
                pass

        env_registered = False
        rc_target = None
        if register_env:
            env_registered, rc_target = self._register_environment_key(token)

        payload: dict[str, Any] = {
            "api_key": token,
            "credentials_file": str(creds_path),
            "environment_registered": env_registered,
        }
        if register_env:
            if sys.platform == "win32":
                payload["activation_guidance"] = (
                    "Restart running Command Prompt or PowerShell terminals to load ED_API_KEY."
                )
            else:
                rc_file = rc_target or ("~/.zshrc" if "zsh" in os.environ.get("SHELL", "") else "~/.bashrc")
                payload["activation_guidance"] = f"source {rc_file}"

        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Generated new API key: {token}")
            print(f"Credentials saved to: {creds_path} (mode 0600)")
            if register_env:
                if env_registered:
                    if sys.platform == "win32":
                        print("Registered ED_API_KEY into Windows user environment.")
                        print("\nTo apply to your current shell session, restart your terminal or run:")
                        print(f"    set ED_API_KEY={token}")
                    else:
                        rc_display = rc_target or ("~/.zshrc" if "zsh" in os.environ.get("SHELL", "") else "~/.bashrc")
                        print(f"Registered ED_API_KEY into user environment ({rc_display}).")
                        print("\nTo apply immediately to your current shell session, run:")
                        print(f"    source {rc_display}")
                        print("    # or")
                        print(f'    export ED_API_KEY="{token}"')
                else:
                    print("Notice: Could not automatically register key into user shell/environment.")
                    print("\nTo apply manually to your current shell session, run:")
                    if sys.platform == "win32":
                        print(f"    set ED_API_KEY={token}")
                    else:
                        print(f'    export ED_API_KEY="{token}"')

        return 0, payload

    def _handle_auth_show(self, args: argparse.Namespace, as_json: bool = False) -> tuple[int, dict[str, Any]]:
        # Check source
        source = "none"
        token = None

        env_key = os.environ.get("ED_API_KEY")
        creds_path = resolve_default_credentials_path()

        if env_key:
            source = "environment (ED_API_KEY)"
            token = env_key.strip()
        elif creds_path.exists():
            try:
                with open(creds_path, encoding="utf-8") as fp:
                    data = json.load(fp)
                    file_token = data.get("api_key")
                    if file_token and isinstance(file_token, str):
                        source = f"file ({creds_path})"
                        token = file_token.strip()
            except Exception:
                pass

        payload = {
            "api_key": token,
            "source": source,
            "credentials_file": str(creds_path),
            "credentials_file_exists": creds_path.exists(),
        }
        if not token:
            payload["remediation"] = (
                "Run 'ed-telemetry auth keygen --register-env' to generate and register credentials."
            )

        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            if token:
                print(f"Active API Key: {token}")
                print(f"Source: {source}")
            else:
                print("No API Key configured (Local loopback unauthenticated mode).")
                print(f"Credentials File: {creds_path} (Not Found)")
                print("\nTo generate and register an API key for network security:")
                print("  ed-telemetry auth keygen --register-env")
        return 0, payload

    def _handle_auth_revoke(self, args: argparse.Namespace, as_json: bool = False) -> tuple[int, dict[str, Any]]:
        creds_path = resolve_default_credentials_path()
        file_removed = False
        if creds_path.exists():
            try:
                creds_path.unlink()
                file_removed = True
            except OSError:
                pass

        env_stripped = self._strip_environment_key()

        payload = {
            "credentials_file_removed": file_removed,
            "environment_stripped": env_stripped,
        }

        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            if file_removed:
                print(f"Removed credentials file: {creds_path}")
            else:
                print(f"No credentials file found at: {creds_path}")
            if env_stripped:
                print("Stripped ED_API_KEY configuration from user shell environment.")
        return 0, payload

    def _register_environment_key(self, token: str) -> tuple[bool, str | None]:
        """Register ED_API_KEY into user shell rc (POSIX) or Windows user environment."""
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["setx", "ED_API_KEY", token],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True, "User Environment"
            except (subprocess.SubprocessError, OSError):
                return False, None

        # POSIX (Linux / macOS)
        shell = os.environ.get("SHELL", "")
        rc_name = ".zshrc" if "zsh" in shell else ".bashrc"
        rc_path = Path.home() / rc_name
        if not rc_path.exists() and rc_name == ".zshrc":
            rc_name = ".bashrc"
            rc_path = Path.home() / ".bashrc"

        block = f'\n# >>> ed-telemetry auth >>>\nexport ED_API_KEY="{token}"\n# <<< ed-telemetry auth <<<\n'

        try:
            content = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
            pattern = re.compile(
                r"# >>> ed-telemetry auth >>>.*?# <<< ed-telemetry auth <<<\n?",
                re.DOTALL,
            )
            if pattern.search(content):
                new_content = pattern.sub(block.lstrip("\n"), content)
            else:
                new_content = content + block

            rc_path.write_text(new_content, encoding="utf-8")
            return True, f"~/{rc_name}"
        except OSError:
            return False, None

    def _strip_environment_key(self) -> bool:
        """Strip ED_API_KEY block from user shell rc files (POSIX) or registry (Windows)."""
        stripped = False
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["reg", "delete", "HKCU\\Environment", "/F", "/V", "ED_API_KEY"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                stripped = True
            except OSError:
                pass
            return stripped

        # POSIX
        for rc_name in (".bashrc", ".zshrc", ".profile"):
            rc_path = Path.home() / rc_name
            if rc_path.exists():
                try:
                    content = rc_path.read_text(encoding="utf-8")
                    pattern = re.compile(
                        r"# >>> ed-telemetry auth >>>.*?# <<< ed-telemetry auth <<<\n?",
                        re.DOTALL,
                    )
                    if pattern.search(content):
                        new_content = pattern.sub("", content)
                        rc_path.write_text(new_content, encoding="utf-8")
                        stripped = True
                except OSError:
                    pass
        return stripped

    def _handle_db(self, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
        """Dispatch db subcommands."""
        action = getattr(args, "db_action", None)
        as_json = getattr(args, "json", False)

        if action == "status":
            return self._handle_db_status(args, as_json=as_json)
        if action == "prune":
            return self._handle_db_prune(args, as_json=as_json)
        if action == "vacuum":
            return self._handle_db_vacuum(args, as_json=as_json)

        print("Usage: ed-telemetry db {status,prune,vacuum} [options]")
        return 0, {}

    def _handle_db_status(self, args: argparse.Namespace, as_json: bool = False) -> tuple[int, dict[str, Any]]:
        if not self._database_stats_port:
            err_msg = "Database stats port is not configured."
            if as_json:
                print(json.dumps({"error": err_msg}))
            else:
                sys.stderr.write(f"[ERROR] {err_msg}\n")
            return 1, {"error": err_msg}

        stats = self._database_stats_port.get_stats()
        payload = {
            "db_path": sanitize_host_path(stats.db_path),
            "file_size_bytes": stats.file_size_bytes,
            "total_events": stats.total_events,
            "oldest_event": stats.oldest_event_timestamp.isoformat() if stats.oldest_event_timestamp else None,
            "newest_event": stats.newest_event_timestamp.isoformat() if stats.newest_event_timestamp else None,
        }

        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            mb_size = stats.file_size_bytes / (1024 * 1024)
            print("Database Storage Status:")
            print(f"  Path:         {payload['db_path']}")
            print(f"  File Size:    {mb_size:.2f} MB ({stats.file_size_bytes:,} bytes)")
            print(f"  Total Events: {stats.total_events:,}")
            oldest_str = (
                stats.oldest_event_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                if stats.oldest_event_timestamp
                else "N/A"
            )
            newest_str = (
                stats.newest_event_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                if stats.newest_event_timestamp
                else "N/A"
            )
            print(f"  Oldest Event: {oldest_str}")
            print(f"  Newest Event: {newest_str}")

        return 0, payload

    def _handle_db_prune(self, args: argparse.Namespace, as_json: bool = False) -> tuple[int, dict[str, Any]]:
        if not self._maintain_database_port:
            err_msg = "Database maintenance port is not configured."
            if as_json:
                print(json.dumps({"error": err_msg}))
            else:
                sys.stderr.write(f"[ERROR] {err_msg}\n")
            return 1, {"error": err_msg}

        days = getattr(args, "days", None)
        max_records = getattr(args, "max_records", None)
        vacuum = getattr(args, "vacuum", False)
        force = getattr(args, "force", False)

        if days is None and max_records is None:
            err_msg = "Must specify at least one pruning criteria: --days <N> or --max-records <N>."
            if as_json:
                print(json.dumps({"error": err_msg}))
            else:
                sys.stderr.write(f"[ERROR] {err_msg}\n")
            return 1, {"error": err_msg}

        if not force and not as_json:
            criteria = []
            if days is not None:
                criteria.append(f"records older than {days} days")
            if max_records is not None:
                criteria.append(f"FIFO oldest exceeding {max_records} total records")
            print(f"Pruning criteria: {', '.join(criteria)}.")
            try:
                confirm = input("Are you sure you want to prune historical telemetry events? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes"):
                    print("Prune aborted.")
                    return 0, {"aborted": True}
            except (KeyboardInterrupt, EOFError):
                print("\nPrune aborted.")
                return 0, {"aborted": True}

        res = self._maintain_database_port.maintain(
            retention_days=days,
            max_records=max_records,
            run_vacuum=vacuum,
        )

        payload = {
            "pruned_count": res.pruned_count,
            "vacuumed": res.vacuumed,
            "initial_size_bytes": res.initial_size_bytes,
            "final_size_bytes": res.final_size_bytes,
            "freed_bytes": max(0, res.initial_size_bytes - res.final_size_bytes),
        }

        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            freed_kb = payload["freed_bytes"] / 1024
            print(f"Prune completed: Removed {res.pruned_count:,} events.")
            if res.vacuumed:
                print(f"Vacuum completed: Freed {freed_kb:.2f} KB disk space.")

        return 0, payload

    def _handle_db_vacuum(self, args: argparse.Namespace, as_json: bool = False) -> tuple[int, dict[str, Any]]:
        if not self._maintain_database_port:
            err_msg = "Database maintenance port is not configured."
            if as_json:
                print(json.dumps({"error": err_msg}))
            else:
                sys.stderr.write(f"[ERROR] {err_msg}\n")
            return 1, {"error": err_msg}

        res = self._maintain_database_port.maintain(
            retention_days=None,
            max_records=None,
            run_vacuum=True,
        )

        payload = {
            "vacuumed": True,
            "initial_size_bytes": res.initial_size_bytes,
            "final_size_bytes": res.final_size_bytes,
            "freed_bytes": max(0, res.initial_size_bytes - res.final_size_bytes),
        }

        if as_json:
            print(json.dumps(payload, indent=2))
        else:
            freed_kb = payload["freed_bytes"] / 1024
            print(f"Vacuum completed: Reclaimed {freed_kb:.2f} KB disk space.")

        return 0, payload
