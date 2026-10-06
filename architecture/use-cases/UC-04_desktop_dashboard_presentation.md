---
title: "Use-Case Specification: UC-04 Desktop Dashboard Presentation"
use_case_id: "UC-04"
status: "draft"
version: "1.0.0"
level: "sea_level"
primary_actor: "Casual Desktop Commander"
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Use-Case Specification: UC-04 Desktop Dashboard Presentation

## 1. Description
The Casual Desktop Commander launches `ed-telemetry` in visual presentation mode to view an on-screen graphical dashboard displaying real-time commander rank progression, current ship status, and live docking state.

---

## 2. Actors
* **Primary Actor:** Casual Desktop Commander
* **Secondary Actors:** Operating System Window Manager (Desktop Environment), Core Telemetry Engine.

---

## 3. Pre-Conditions
1. Graphical display context available (X11, Wayland, or Windows Desktop).
2. Package installed with desktop presentation dependencies.

---

## 4. Basic Flow (Main Success Scenario)
1. Commander invokes command: `ed-telemetry app`.
2. System initializes `ed_app.bootstrap.build_engine()`.
3. System initializes presentation view adapter (`ed_app.ui.runner`).
4. System launches desktop window displaying status widgets and live event ticker.
5. Presentation view subscribes to state change events emitted by the core engine.
6. As the commander plays Elite Dangerous, the view updates without user intervention:
   - System jumps update current solar system name.
   - Docking events update station name and available services.
7. Commander closes window.
8. System shuts down cleanly and exits with code 0.

---

## 5. Alternative Flows
* **1a. Headless Environment (Missing Display):**
  1. System detects missing `$DISPLAY` on Linux or headless container environment.
  2. System emits error: `Error: No graphical display detected. Use 'ed-telemetry watch' for headless mode.`
  3. System exits cleanly with code 1.

---

## 6. Post-Conditions
* Commander observes real-time telemetry visually without locking business logic into UI rendering loops.
