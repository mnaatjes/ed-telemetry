---
title: "Security & Sensitive Data Leakage Audit (Endpoints & SQLite)"
tags: ["security", "audit", "pii", "endpoints", "sqlite", "credentials"]
created_at: "2026-10-26"
last_updated_at: "2026-10-26"
---

# Security & Sensitive Data Leakage Audit: Endpoints & SQLite Database

This security assessment audits all active driving HTTP/SSE endpoints and persistent SQLite database records (`telemetry.db`) emitted by the `ed-telemetry` service on `michael-desktop` (`192.168.1.214:8080`).

---

## 1. Executive Summary

| Security Category | Severity | Finding Count | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication Secrets & Tokens** | High | 0 | **PASSED** | Zero API keys, Bearer tokens, Frontier OAuth tokens, or private keys found. |
| **System Credentials & Passwords** | Critical | 0 | **PASSED** | Zero credentials or passwords stored in database or emitted via endpoints. |
| **Host System Path Leakage** | Medium | 41 instances | **IDENTIFIED** | Linux filesystem username and Steam installation paths exposed in endpoints. |
| **PII & Player Identifiers** | Low / Medium | 31 instances | **IDENTIFIED** | Frontier ID (`FID`), Commander Name, and friend names stored in raw event payloads. |
| **Network & Transport Exposure** | Medium | 1 instance | **IDENTIFIED** | HTTP endpoints bind to `0.0.0.0` with permissive CORS (`*`) and unauthenticated read access. |

---

## 2. Methodology & Scan Coverage

### Target Artifacts
1. **Persistent SQLite Database:** 531 records scanned across `telemetry_events` table (`~/.local/share/ed-telemetry/telemetry.db`).
2. **HTTP Endpoints Scanned:**
   - `GET /api/v1/health`
   - `GET /api/v1/status`
   - `GET /api/v1/status/game`
   - `GET /api/v1/events`
   - `GET /api/v1/diagnostics/logs`
   - `GET /api/v1/stream` (SSE live feed)

### Automated Pattern Detection Regex Rules
- **Private Keys:** `-----BEGIN (RSA|OPENSSH|EC|DSA|PGP)? PRIVATE KEY-----`
- **Secrets & API Tokens:** `(?i)(api[_-]?key|secret|token|password|bearer|auth|authorization|credential)[\"'\s:=]+[A-Za-z0-9_\-\.]{8,}`
- **Frontier OAuth:** `(?i)(auth[_-]?token|frontier[_-]?token|oauth)`
- **Email Addresses:** `[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`
- **Absolute Local Paths:** `/(?:home|etc|var|usr|drive_c)/[a-zA-Z0-9._/-]+`
- **Player Account Identifiers:** `(?i)\b(FID|Commander|FrontierID)\b`
- **Steam 64-bit IDs:** `\b7656119\d{10}\b`

---

## 3. Detailed Findings

### Finding 1: Zero Secrets or Authentication Tokens (Passed)
- **Evaluation:** Neither the journal ingestion pipeline nor SQLite persistence captures authorization headers, CAPI tokens, or OAuth secrets.
- **Result:** No cryptographic material, private keys, or passwords exist in the store. Game version strings like `4.4.2.1` matched naive IP regex scanners but were confirmed to be game build versions, not network IPs.

### Finding 2: Host Filesystem Path Exposure (Medium Severity)
- **Description:** Absolute host filesystem paths containing the operating system username (`/home/michael/...`) are surfaced in multiple locations:
  1. `GET /api/v1/status`: Surfaces `monitored_directory` (`/home/michael/.steam/debian-installation/steamapps/...`).
  2. `GET /api/v1/status/game`: Surfaces `target_path` (`/home/michael/.../Status.json`).
  3. `telemetry.audit` events in SQLite and `/api/v1/stream`: Surfaces journal target paths with host user directories.
- **Risk:** Exposes the host operating system username (`michael`), Proton prefix architecture, and directory topology to any network client on the LAN.
- **Remediation:** Provide an optional path sanitization / anonymization flag (e.g., `--sanitize-paths` or `ED_SANITIZE_PATHS=true`) replacing `/home/<user>` with `~` or `<HOME>`.

### Finding 3: Player Account & Social Graph PII (Low/Medium Severity)
- **Description:** Frontier developments journals log player identifiers and social connections:
  - `Commander`: Exposes Commander Name (`adulantis`) and Frontier Customer ID (`FID: F5611068`).
  - `Friends`: Exposes player friend list events if social actions occur while playing.
  - `ReceiveText`: Exposes in-game direct player-to-player communications.
- **Risk:** If the endpoint is exposed on a shared network or port-forwarded, unauthorized observers can track player online status, financial balance (`5,235,083,083` credits), current star system coordinates, and carrier movements.
- **Remediation:**
  1. Filter out `Friends` and `ReceiveText` event types from SQLite persistence and default SSE streaming unless explicitly opted into via `--include-social`.
  2. Implement an optional privacy mask for `FID` and `Commander` in public-facing stream deployments.

### Finding 4: Unauthenticated Network Binding & Permissive CORS (Medium Severity)
- **Description:** When running with `--host 0.0.0.0`:
  - `Access-Control-Allow-Origin: *` is returned on all responses.
  - Zero authentication or API key checks exist on REST or SSE endpoints.
- **Risk:** Any web browser on the local network (or malicious cross-origin website visited on the same machine) can issue `fetch()` calls to `http://192.168.1.214:8080/api/v1/*` to harvest location and player status.
- **Remediation:**
  1. Restrict default binding to `127.0.0.1` unless explicitly requested.
  2. Add optional shared bearer token authentication (`--api-key` / `ED_API_KEY`) for multi-host homelab deployments.

---

## 4. Remediation Action Matrix

| Issue | Recommended Action | Planned Phase |
| :--- | :--- | :--- |
| **Path Exposure** | Mask `/home/<user>` in `AuditAction` DTOs and API status serializers | Minor Release |
| **Social Event Leakage** | Drop or sanitize `ReceiveText` and `Friends` journal events | Minor Release |
| **Endpoint Auth** | Introduce optional basic bearer token authentication | Minor Release |
