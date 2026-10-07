# Elite Dangerous Telemetry (`ed-telemetry`)
\
**Version:** `v0.2.0` (Inception / Elaboration Phase)

A modern, modular monorepo providing a decoupled, headless telemetry engine, file watcher, and multi-adapter interface (CLI, FastAPI REST, MCP Server) for the *Elite Dangerous* galaxy.

---

## Workspace Architecture

```text
ed-telemetry/
|-- pyproject.toml              # Minimal workspace configuration
|-- .github/                    # CI/CD automation pipelines
|-- packages/                   # Decoupled domain packages
|   |-- ed_domain/              # Pure domain models, enums, and journal event schemas
|   |-- ed_watcher/             # Dedicated headless journal file watcher
|   |-- ed_egress/              # Outbound service adapters (EDDN, Inara, EDSM)
|   |-- ed_sdk/                 # Testing harness and MockJournalWriter
|   \-- ed_server/              # Headless CLI, FastAPI REST, and MCP server
|-- architecture/               # Unified Process (UP) engineering plane
|-- docs/                       # Diátaxis customer/operator documentation plane
\-- tests/                      # Fast headless unit & integration test suites
```
