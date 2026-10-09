# Elite Dangerous Telemetry (`ed-telemetry`)
\
**Version:** `v0.3.0` (Inception / Elaboration Phase)

A modern, modular monorepo providing a decoupled, headless telemetry engine, file watcher, and multi-adapter interface (CLI, FastAPI REST, MCP Server) for the *Elite Dangerous* galaxy.

---

## Workspace Architecture

```text
ed-telemetry/
│
├── src/                                         # PRODUCTION APPLICATION RUNTIME (Pure Hexagonal)
│   │
│   ├── domain/                                  # 100% PURE CORE (Hexagon Center / Invariant A)
│   │   ├── engine.py                            # Core TelemetryEngine state coordinator
│   │   ├── ports/                               # Pure abstract boundary contracts
│   │   │   ├── watcher.py                       # WatcherPort (inbound telemetry source)
│   │   │   └── egress.py                        # EgressPort (outbound data sink)
│   │   └── py.typed
│   │
│   ├── services/                                # APPLICATION SERVICE LAYER (Use Cases / Invariant D)
│   │   ├── bootstrap.py                         # Composition Root (Dependency Injection factory)
│   │   ├── context.py                           # ApplicationContext (Immutable service container)
│   │   ├── base.py                              # BaseApplicationService protocol
│   │   ├── exceptions.py                        # ApplicationServiceError hierarchy
│   │   ├── watcher.py                           # WatcherService (queries WatcherPort)
│   │   └── dto/                                 # Boundary Data Transfer Objects (Invariant C & E)
│   │       ├── base.py                          # DataTransferObject protocol
│   │       └── watcher.py                       # WatcherStatusDTO (immutable query projection)
│   │
│   ├── infrastructure/                          # DRIVEN ADAPTERS (Secondary / External I/O / Invariant G)
│   │   ├── watcher/                             # Inbound Journal & State File Monitor Adapter
│   │   │   ├── watcher.py                       # FileSystemWatcher (Background daemon thread)
│   │   │   ├── selector.py                      # Active Journal candidate selection & sorting
│   │   │   ├── discovery/                       # Cross-platform OS path discovery (Linux/Win)
│   │   │   │   ├── coordinator.py               # PathDiscoverer coordinator
│   │   │   │   └── strategies/                  # OS-specific probing strategies (Proton/Registry)
│   │   │   ├── engine/                          # Low-level I/O & Ingestion Reactor
│   │   │   │   ├── reactor.py                   # Reactive hybrid event loop & heartbeat ticker
│   │   │   │   ├── tailer.py                    # Non-blocking JSONL line streaming
│   │   │   │   ├── snapshot_reader.py           # Zero-byte atomic truncation guards
│   │   │   │   ├── freshness.py                 # BLAKE2b 64-bit deduplication gate
│   │   │   │   ├── envelopes.py                 # Ingestion & Audit event data structures
│   │   │   │   ├── receiver.py                  # Stream consumer callback sink
│   │   │   │   └── stream_context.py            # Active journal stream tracking context
│   │   │   ├── snapshots/                       # Game snapshot catalog & normalization
│   │   │   │   ├── registry.py                  # Canonical snapshot catalog
│   │   │   │   └── identifier.py                # Case-folding & POSIX collision resolver
│   │   │   └── exceptions.py                    # WatcherError domain exceptions
│   │   │
│   │   └── egress/                              # Outbound Transmitter Adapters
│   │       └── transmitter.py                   # NullTransmitter (EDDN/Inara placeholder)
│   │
│   └── interfaces/                              # DRIVING SURFACES (Primary Adapters / Front Doors)
│       ├── __main__.py                          # Python executable module runner (python -m interfaces)
│       └── cli/                                 # Headless CLI entrypoint & daemon runner
│           └── main.py                          # ed-telemetry console script entrypoint
│
├── sdk/                                         # SATELLITE DEVELOPMENT KIT (Simulation / Invariant B)
│   ├── mock_writer.py                           # Synthetic journal generator & simulation harness
│   └── py.typed
│
├── tests/                                       # VERIFICATION SUITE
│   └── unit/                                    # Unit, contract, and cross-platform Wine test suites
│
├── scripts/                                     # CI/CD & VERIFICATION TOOLING
│   ├── verify.py                                # Tier 2 Quality Gate orchestrator
│   ├── run_wine_tests.sh                        # Windows NT / Wine test execution script
│   ├── print_dependency_graph.py                # AST dependency & boundary graph inspector
│   └── guard_release_branch.py                  # Release branch enforcement hook
│
├── architecture/                                # ENGINEERING GOVERNANCE (ADRs, SDDs, RFCs)
└── docs/                                        # DIÁTAXIS OPERATOR PLANE (Runbooks, References)
```
