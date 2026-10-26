---
title: "Proposed Security & Privacy Controls: Permissions and Sensitive Payloads"
tags: ["security", "privacy", "permissions", "sqlite", "sensitive-data"]
created_at: "2026-10-26"
last_updated_at: "2026-10-26"
---

# Proposed Security & Privacy Controls: Permissions and Sensitive Payloads

## 1. Local Database Permissions Hardening

To prevent unauthorized read access by other non-privileged user accounts or co-located processes on multi-user Unix workstations, local persistence storage must strictly enforce POSIX file mode constraints upon creation and initialization:

* **Parent Directory (`~/.local/share/ed-telemetry/`):** Must be initialized with `0700` (`rwx------`) permissions.
* **SQLite Database Files (`telemetry.db`, `telemetry.db-wal`, `telemetry.db-shm`):** Must be initialized and enforced with `0600` (`rw-------`) permissions.
* **Diagnostic Log Files (`~/.local/state/ed-telemetry/ed-telemetry.log*`):** Must be initialized with `0600` (`rw-------`) permissions.

---

## 2. Sensitive Telemetry Properties & Payloads

| Data / Property Category | Target Fields & Events | Exposure Vector | Security & Privacy Impact | Protective Handling |
| :--- | :--- | :--- | :--- | :--- |
| **Root Billing Account (FID)** | `FID` (in `Commander`, `LoadGame` events) | `/api/v1/stream`<br>`/api/v1/events`<br>SQLite DB | Frontier account ID (`customer_id`). Correlates Commander resets and real-world billing across platforms. | Preserve locally in SQLite (`0600`); require `--api-key` on network API; mask on public streams. |
| **Player Identity & Persona** | `Commander`, `Name` (in `Commander`, `LoadGame`) | `/api/v1/stream`<br>`/api/v1/events`<br>`/api/v1/status/game` | Public Commander name. Enables tracking, target-marking in Open Play, and profile harvesting. | Preserve for Inara/EDSM; require `--api-key` over network; mask if `--redact-pii` is enabled. |
| **Player-to-Player Comms** | `Message`, `From`, `Channel` (in `ReceiveText`, `SendText`) | `/api/v1/stream`<br>`/api/v1/events` | Private player DMs, Wing/Squadron chat. Risks leaking Discord links, passwords, and private communications. | Segregate into dedicated topic (`telemetry.comms`); opt-in subscription only; never stream unauthenticated. |
| **Social Presence & Graph** | `Friends` event (`Name`, `Status`) | `/api/v1/stream`<br>`/api/v1/events` | Real-time online status and friend lists of third-party players without their consent. | Segregate into `telemetry.social`; default-off in public relays. |
| **Host System Topography** | `target_path`, `monitored_directory`, `ed-telemetry.log` paths | `/api/v1/status`<br>`/api/v1/status/game`<br>`telemetry.audit` | Discloses Linux OS username (`/home/michael/...`), Proton prefix layout, and filesystem structure. | Sanitize path prefixes (`~/...` or `<SAVED_GAMES>/...`) in API status serialization. |
| **Financial & Assets State** | `Balance`, `Credits`, `Loan` (in `Status.json`, `LoadGame`) | `/api/v1/status/game`<br>`/api/v1/stream` | Current liquid credit balance (e.g. `5,235,083,083`). Target profiling for pirates and stream-snipers. | Preserve in local DB; guard behind `--api-key` when binding `0.0.0.0`. |
| **Strategic Movement & Tactical Coordinates** | `CarrierJumpRequest`, `FSDTarget`, `Latitude`, `Longitude` | `/api/v1/stream`<br>`/api/v1/events` | Fleet Carrier jump timing, lock timers, orbital surface coordinates, combat rally points. | High stream-sniping risk; require authenticated access over LAN. |
