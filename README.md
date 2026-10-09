# Elite Dangerous Telemetry (`ed-telemetry`)
\
**Version:** `v0.2.0` (Inception / Elaboration Phase)

A modern, modular monorepo providing a decoupled, headless telemetry engine, file watcher, and multi-adapter interface (CLI, FastAPI REST, MCP Server) for the *Elite Dangerous* galaxy.

---

## Workspace Architecture

```text
ed-telemetry/
|-- pyproject.toml              # Build configuration & architectural boundary contracts
|-- .github/                    # CI/CD automation pipelines
|-- src/                        # Pure Hexagonal Application Topology
|   |-- domain/                 # Pure domain models, enums, engine, and boundary ports
|   |-- services/               # Application Service Layer (orchestration, DTOs, context)
|   |-- infrastructure/         # Driven secondary adapters (watcher, egress)
|   \-- interfaces/             # Driving primary surfaces (CLI, API, MCP)
|-- sdk/                        # Satellite development harness and MockJournalWriter
|-- architecture/               # Unified Process (UP) engineering plane
|-- docs/                       # Diátaxis customer/operator documentation plane
\-- tests/                      # Fast headless unit & integration test suites
```
