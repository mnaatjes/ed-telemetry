---
title: "Use-Case Discipline Governance and Index"
tags: ["architecture", "use-cases", "requirements", "governance"]
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Use-Case Discipline Governance and Index

Governed by the Rational Unified Process (RUP) Use-Case Specification standard and Alistair Cockburn's Goal-Level Hierarchy.

---

## 1. Principles & Quality Gates

1. **Black-Box System Boundary:** Specify what the system performs externally (observable telemetry, inputs, and events), omitting private internal classes.
2. **Sea-Level Scoping (User Goal):** Must satisfy the *Coffee Break Test*: an elementary workflow performed in a single session by a primary actor delivering distinct business value.
3. **Decomposition:**
   * Main Success Scenario (Basic Flow).
   * Extension / Alternate Flows (numbered e.g. `3a`, `4b`).
   * Formal Pre-conditions and Post-conditions.

---

## 2. Registered Specifications

| Use-Case ID | Title | Level | Primary Actor | Status | File |
| :---: | :--- | :---: | :--- | :---: | :--- |
| **UC-01** | Headless Journal Monitoring | Sea-Level | Terminal Operator | draft | [UC-01_headless_journal_monitoring.md](UC-01_headless_journal_monitoring.md) |
| **UC-02** | Serve Telemetry REST API & WebSockets | Sea-Level | Streamer / Web Integrator | draft | [UC-02_serve_telemetry_rest_api.md](UC-02_serve_telemetry_rest_api.md) |
| **UC-03** | AI Agent MCP Tool Invocation | Sea-Level | AI Co-Pilot / Assistant | draft | [UC-03_ai_agent_mcp_tool_invocation.md](UC-03_ai_agent_mcp_tool_invocation.md) |
| **UC-04** | Desktop Dashboard Presentation | Sea-Level | Casual Desktop Commander | draft | [UC-04_desktop_dashboard_presentation.md](UC-04_desktop_dashboard_presentation.md) |
