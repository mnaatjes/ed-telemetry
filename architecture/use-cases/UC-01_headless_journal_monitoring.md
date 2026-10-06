---
title: "Use-Case Specification: UC-01 Headless Journal Monitoring"
use_case_id: "UC-01"
status: "draft"
version: "1.0.0"
level: "sea_level"
primary_actor: "Terminal Operator / Homelabber"
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Use-Case Specification: UC-01 Headless Journal Monitoring

## 1. Description
The Terminal Operator launches `ed-telemetry` in headless daemon mode to automatically monitor local Elite Dangerous journal logs and forward live telemetry events to external community networks (EDDN, Inara) without opening a graphical user interface or requiring X11 display hardware.

---

## 2. Actors
* **Primary Actor:** Terminal Operator / Homelabber / Docker Host
* **Secondary Actors:** Elite Dangerous Game Client (writes local logs), EDDN Gateway, Inara API.

---

## 3. Pre-Conditions
1. Python 3.11+ environment with `ed-telemetry` installed.
2. Elite Dangerous Journal log directory exists and is accessible.

---

## 4. Basic Flow (Main Success Scenario)
1. Operator invokes command: `ed-telemetry watch --journal-dir /path/to/logs`.
2. The system executes `ed_app.bootstrap.build_engine()` to wire the Composition Root.
3. The system validates the journal path and identifies the most recent journal log file.
4. The system starts the file watcher in background monitoring mode.
5. When the game client appends a JSON event line to the active log, the watcher captures the line.
6. The system parses the line into a typed domain event (`ed_domain.models.TelemetryEvent`).
7. The system dispatches the event to registered outbound transmitters (`EDDNTransmitter`, `InaraTransmitter`).
8. The system logs a one-line summary to stdout indicating successful transmission.
9. Steps 5–8 repeat until the operator terminates the process (SIGINT/SIGTERM).
10. The system cleanly releases file handles and exits with code 0.

---

## 5. Alternative Flows
* **4a. Journal Directory Missing:**
  1. System detects path does not exist.
  2. System emits error message: `Error: Journal directory not found: <path>`.
  3. System exits with code 1.
* **7a. Network Egress Unavailable:**
  1. System encounters network timeout or HTTP error when dispatching to EDDN/Inara.
  2. System logs a warning with retry backoff.
  3. System does not crash; file watcher continues monitoring subsequent events.

---

## 6. Post-Conditions
* Live telemetry events are safely streamed to external community networks.
* Zero GUI windows or `$DISPLAY` server dependencies are spawned.
