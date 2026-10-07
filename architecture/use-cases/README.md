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

| ID | Title | Status | Date | Primary Actor |
| :---: | :--- | :---: | :---: | :--- |
| **UC-0002** | [UC-0002: Resolve Elite Dangerous Game Journal Directory](0002_discover_game_directory.md) | **draft** | 2026-10-07 | Application Bootstrap |

