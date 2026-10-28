# Elite Dangerous Telemetry (`ed-telemetry`)

**Version:** `v0.6.6` (Beta - Host Testing Candidate)

A modern, decoupled Elite Dangerous telemetry daemon, persistent event store, and multi-adapter interface (CLI, HTTP REST, Server-Sent Events) engineered strictly according to Hexagonal Architecture (Ports and Adapters).

---

## 1. Architectural Topology

The codebase is organized in `src/ed_telemetry/` into pure hexagonal layers:

```text
src/ed_telemetry/
│
├── core/                                        # PURE DOMAIN & APPLICATION CORE
│   ├── domain/                                  # Pure domain entities, value objects, exceptions
│   │   ├── exceptions.py                        # Core domain error hierarchy
│   │   ├── health.py                            # Health check entities
│   │   └── models.py                            # Domain business abstractions
│   │
│   ├── ports/                                   # ABSTRACT BOUNDARY CONTRACTS
│   │   ├── driving/                             # Inbound / Primary port protocols
│   │   │   └── telemetry_port.py                # Use-case ports (Watcher, Ingestion, API, CLI)
│   │   ├── driven/                              # Outbound / Secondary port protocols
│   │   │   └── telemetry_driven_port.py         # Infrastructure ports (Watcher, Egress, SQLite, Logging)
│   │   └── dto/                                 # Boundary Data Transfer Objects
│   │       └── telemetry_dto.py                 # Frozen, immutable DTO definitions
│   │
│   └── use_cases/                               # APPLICATION INTERACTORS
│       ├── get_watcher_status.py                # Query watcher state
│       ├── process_telemetry_stream.py          # Continuous ingestion & audit bubbling
│       ├── sync_journal_snapshot.py             # Point-in-time synchronization
│       ├── find_journal_path.py                 # OS journal discovery
│       ├── get_journal_files.py                 # Journal file enumeration
│       ├── get_latest_game_status.py            # Cockpit Status.json inspection
│       ├── get_auxiliary_snapshot.py            # Market, Cargo, NavRoute lookup
│       ├── get_telemetry_events.py              # In-memory event drain
│       ├── find_telemetry_events.py             # SQLite WAL historical query
│       ├── get_telemetry_stream.py              # Live payload iterator
│       └── get_diagnostic_logs.py               # In-memory diagnostic log snapshots
│
├── adapters/                                    # CONCRETE INFRASTRUCTURE ADAPTERS
│   ├── driving/                                 # Inbound drivers (Front Doors)
│   │   ├── cli/                                 # Zero-dependency terminal interface
│   │   │   └── main.py                          # ed-telemetry CLI entrypoint
│   │   └── api/                                 # Zero-dependency HTTP & SSE server
│   │       └── server.py                        # ThreadingHTTPServer & SSE streamer
│   │
│   └── driven/                                  # Outbound infrastructure sinks
│       ├── watcher/                             # Journal tailer, reactor, and OS discovery
│       ├── persistence/                         # Thread-safe SQLite persistence adapter
│       │   └── sqlite_adapter.py                # WAL mode repository and egress sink
│       ├── logging/                             # Thread-safe diagnostic ring buffer
│       │   └── buffer.py                        # DiagnosticLogBuffer handler
│       └── egress/                              # Broadcast egress sinks
│           ├── buffered_queue.py                # In-memory FIFO ring buffer
│           └── composite.py                     # Fan-out dispatcher
│
└── bootstrap/                                   # COMPOSITION ROOT
    └── container.py                             # Dependency injection graph & logging setup
```

---

## 2. Installation & Quick Start

Requires **Python 3.11+** with **zero runtime third-party dependencies**.

### Option A: Install via Pip Directly from GitHub (Recommended for Operators)
Install the latest release directly into your active Python environment or toolchain:
```bash
pip install git+https://github.com/mnaatjes/ed-telemetry.git@v0.6.6
```

### Option B: Isolated CLI Execution via `pipx` (Recommended for Headless Systems & Steam Deck)
Execute `ed-telemetry` in an isolated virtual environment without polluting system Python:
```bash
# Install globally in isolated container
pipx install git+https://github.com/mnaatjes/ed-telemetry.git

# Or run directly without prior installation
pipx run --spec git+https://github.com/mnaatjes/ed-telemetry.git ed-telemetry --help
```

### Option C: Build and Install from Source Wheel
```bash
# Build standard Python wheel
python3 -m pip install --upgrade build
python3 -m build

# Install the built artifact
pip install dist/ed_telemetry-0.4.0-py3-none-any.whl
```

### Option D: Local Development Setup (Editable Mode)
```bash
# Clone the repository
git clone https://github.com/mnaatjes/ed-telemetry.git
cd ed-telemetry

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .

# (Optional) Install development and quality gate tooling
pip install -e ".[dev]"
```

---

## 3. CLI Command Suite

The `ed-telemetry` CLI provides tools for daemon operation, inspection, and log monitoring:

### Start the Daemon
Run the background telemetry daemon with SQLite persistence and the HTTP REST / SSE API:
```bash
ed-telemetry serve --host 127.0.0.1 --port 8080 --log-level INFO
```

### Inspect Operational Status
```bash
# Check watcher operational state and discovered directory
ed-telemetry status

# Inspect real-time player cockpit status (Status.json)
ed-telemetry status game

# Format output as machine-readable JSON
ed-telemetry status --json
```

### Query Historical Telemetry
Query events persisted in the SQLite WAL store:
```bash
ed-telemetry events --limit 20 --topic telemetry.journal
```

### View Diagnostic Logs & Audit Streams
```bash
# Query recent in-memory application logs
ed-telemetry logs --level WARNING --limit 50

# Follow live telemetry events and error bubbling in real-time
ed-telemetry tail --topic telemetry.audit
```

---

## 4. HTTP REST & Server-Sent Events (SSE) API

When `ed-telemetry serve` is active, the API listens on `http://127.0.0.1:8080/api/v1`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service health status |
| `GET` | `/api/v1/status` | Ingestion watcher state and monitored paths |
| `GET` | `/api/v1/status/game` | Cockpit snapshot (`Status.json`) |
| `GET` | `/api/v1/snapshots/{name}` | Auxiliary game snapshots (`market`, `cargo`, `navroute`) |
| `GET` | `/api/v1/events` | Historical SQLite events (`?topic=...&since_id=...&limit=...`) |
| `GET` | `/api/v1/events/buffer` | Drain recent in-memory event buffer |
| `GET` | `/api/v1/stream` | Real-time Server-Sent Events (SSE) event stream |
| `GET` | `/api/v1/diagnostics/logs` | Diagnostic log snapshot (`?min_level=...&limit=...`) |
| `POST` | `/api/v1/control/watch` | Control watcher lifecycle (`{"action": "start"|"stop"}`) |

---

## 5. Verification & Testing

Execute Tier 2 Quality Gates locally:
```bash
# Run pre-commit formatting, import-linter contracts, mypy, and pytest
python scripts/verify.py

# Run Windows NT verification under Wine
./scripts/run_wine_tests.sh
```

---

## 6. Documentation Directory (Diátaxis)

* [**How-To Guides (`docs/how-to/`)**](docs/how-to/README.md) — Operational runbooks for running the daemon, querying logs, and consuming the API.
* [**Technical Reference (`docs/reference/`)**](docs/reference/README.md) — Detailed specifications for CLI commands, REST/SSE endpoints, and hexagonal rules.
