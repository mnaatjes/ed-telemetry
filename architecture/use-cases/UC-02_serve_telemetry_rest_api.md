---
title: "Use-Case Specification: UC-02 Serve Telemetry REST API and WebSockets"
use_case_id: "UC-02"
status: "draft"
version: "1.0.0"
level: "sea_level"
primary_actor: "Streamer / Web Integrator"
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Use-Case Specification: UC-02 Serve Telemetry REST API and WebSockets

## 1. Description
The Streamer or Web Developer starts the local FastAPI server to expose real-time commander state, system coordinates, and telemetry streams over HTTP and WebSockets for custom web dashboards, OBS overlays, or third-party web apps.

---

## 2. Actors
* **Primary Actor:** Streamer / Web Dashboard Integrator
* **Secondary Actors:** Web Browser, OBS Studio Browser Source, Third-Party Desktop Utilities.

---

## 3. Pre-Conditions
1. Package installed with server extra: `pip install ed-telemetry[server]`.
2. Port (default `8000`) is available on `localhost`.

---

## 4. Basic Flow (Main Success Scenario)
1. Integrator invokes command: `ed-telemetry serve --api --port 8000`.
2. System executes `ed_app.bootstrap.build_engine()` to wire the core engine.
3. System mounts the FastAPI application (`ed_app.api.server`).
4. System launches Uvicorn server bound to `127.0.0.1:8000`.
5. Integrator opens browser to `http://localhost:8000/docs` to inspect interactive OpenAPI documentation.
6. Integrator connects a client to WebSocket endpoint: `ws://localhost:8000/api/v1/stream`.
7. As telemetry events occur, the system broadcasts JSON events over the WebSocket connection.
8. Integrator queries REST endpoint: `GET /api/v1/cmdr/status`.
9. System returns cached commander state as JSON (rank, ship, current system).
10. Steps 7–9 continue until operator issues SIGINT to terminate the server.

---

## 5. Alternative Flows
* **1a. Missing Server Dependencies:**
  1. System detects `fastapi` or `uvicorn` is not installed.
  2. System emits guidance message: `Error: Server dependencies missing. Run 'pip install ed-telemetry[server]'`.
  3. System exits with code 1.
* **4a. Port Conflict:**
  1. System detects port 8000 is already in use.
  2. System emits error: `Error: Port 8000 is already bound. Specify --port <num>`.
  3. System exits with code 1.

---

## 6. Post-Conditions
* Real-time game state is securely accessible over local HTTP and WebSocket endpoints.
