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

### 1.1 Technical Implementation Mechanics
Within `ed-telemetry`, permissions are enforced entirely in Python standard library (`os`, `pathlib`, `stat`) without external tooling:

1. **POSIX File Mode Enforcement at Initialization:**
   In `SqlitePersistenceManager.__init__()` and path setup routines:
   ```python
   # Enforce user-only directory permissions
   self.db_path.parent.mkdir(parents=True, exist_ok=True)
   if os.name == "posix":
       os.chmod(self.db_path.parent, 0o700)
       if self.db_path.exists():
           os.chmod(self.db_path, 0o600)
   ```
2. **Preemptive Creation Masking:**
   Ensure files created by SQLite or logging handlers inherit restricted access by temporarily setting `os.umask(0o077)` during directory and initial file descriptor creation, or explicitly invoking `os.chmod(f, 0o600)` immediately following connection/handler setup.
3. **Cross-Platform Graceful Handling:**
   Under Windows NTFS, POSIX bitmask operations (`0o600`) are no-ops or map to the user's ACL. Enclosing in `if os.name == "posix":` guarantees full cross-platform compatibility across Windows, Linux, and Wine simulation without raising exceptions.

### 1.2 Impact on Userflow and Operation
Enforcing these permissions has **zero negative friction** on the operator userflow:

* **Installation (`pip`, `pipx`):** No impact. `pipx install git+https://github.com/...` runs unprivileged in user-space.
* **Running CLI Subcommands (`serve`, `status`, `events`, `stream`):** No impact. The commands run under the user's own UID (`michael`), retaining full read/write access to both `0700` directories and `0600` files.
* **Sudo / Root Privileges:** **Not required.** The operator does not need `sudo` or elevated permissions to create, read, or chmod files inside their own `~/.local/share/` and `~/.local/state/` directories.
* **Multi-User Protection:** If another user account (`guest`, `ansible_runner`, or a co-located container) inspects `/home/michael/.local/share/ed-telemetry/`, the OS filesystem kernel denies directory traversal (`Permission denied`), preventing any unauthorized inspection of the database or logs.

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

---

## 3. Perimeter Network Guarding: HTTP & SSE API Authentication (`--api-key`)

To secure network-exposed instances (such as when running with `--host 0.0.0.0`) without breaking downstream consumers, `ed-telemetry` implements **Perimeter Network Guarding**. Instead of encrypting local SQLite files (which adds complexity and breaks downstream access), the network transport itself serves as the security perimeter.

### 3.1 Invocation & Configuration
Operators configure the API key via CLI flag or environment variable:

```bash
ed-telemetry serve --host 0.0.0.0 --port 8080 --api-key "my-secret-token"
# Or via environment variable:
ED_API_KEY="my-secret-token" ed-telemetry serve --host 0.0.0.0 --port 8080
```

* **Local Mode (Default):** If `--api-key` is omitted and the server binds to `127.0.0.1`, requests are treated as local-trusted.
* **Network Mode:** If `--api-key` is provided (or if binding to non-loopback `0.0.0.0` with key enforcement enabled), all endpoints require authentication.

### 3.2 Authentication Handshake & Presentation Mechanisms
Clients can present credentials via three standard HTTP channels:

1. **HTTP Authorization Header (Primary for REST / CLI):**
   ```http
   GET /api/v1/status HTTP/1.1
   Host: 192.168.1.214:8080
   Authorization: Bearer my-secret-token
   ```
2. **Custom Header (`X-API-Key`):**
   ```http
   GET /api/v1/events HTTP/1.1
   Host: 192.168.1.214:8080
   X-API-Key: my-secret-token
   ```
3. **Query Parameter (Browser `EventSource` / SSE Compatibility):**
   Browser JavaScript standard `new EventSource('/api/v1/stream')` cannot transmit custom HTTP request headers. To enable browser dashboards without third-party polyfills, query parameter authentication is accepted:
   ```http
   GET /api/v1/stream?api_key=my-secret-token HTTP/1.1
   ```

### 3.3 Server-Side Validation Pipeline (`server.py`)
Inside `TelemetryHttpHandler`:
1. Check if server-level `api_key` is set. If not, bypass authentication.
2. Extract token from `Authorization: Bearer <token>`, `X-API-Key`, or `?api_key=<token>`.
3. Compare using constant-time string comparison (`hmac.compare_digest`) to prevent side-channel timing attacks.
4. **Rejection:** If token is missing or mismatched, reject immediately with `HTTP 401 Unauthorized` and an RFC 7807 problem details JSON payload:
   ```json
   {
     "type": "about:blank",
     "title": "Unauthorized",
     "status": 401,
     "detail": "Invalid or missing API key."
   }
   ```
5. **Acceptance:** If valid, request execution proceeds normally to domain use cases or the live SSE streaming loop.

### 3.4 Host Path Masking
When responding over the API, absolute local paths containing the operating system username (`/home/michael/...`) are sanitized:
* In `GET /api/v1/status`: `monitored_directory` is displayed as `~/.../Frontier Developments/Elite Dangerous`.
* In `GET /api/v1/status/game`: `target_path` is displayed as `~/.../Status.json`.
* In `telemetry.audit`: Local paths are truncated or prefix-masked before transmission over the network.

### 3.5 Cross-Platform API Key Management & Utility CLI Workflow

To minimize operational friction without corrupting shell configuration files (such as `~/.bashrc` or `~/.zshrc`) or relying on fragile Windows Registry edits, `ed-telemetry` adopts a **Canonical Credentials File & Precedence Discovery** architecture.

#### 1. Canonical Storage Locations
API keys generated or managed by the CLI reside strictly in standard per-user configuration paths:

| Platform | Canonical Path | Permission Invariant |
| :--- | :--- | :--- |
| **Linux / Steam Deck** | `~/.config/ed-telemetry/credentials.json` | `chmod 0600` (file), `0700` (directory) |
| **Windows** | `%LOCALAPPDATA%\ed-telemetry\credentials.json` | Native NTFS user ACL inheritance |

File schema:
```json
{
  "api_key": "ed_sec_a3f89b21c4e7...",
  "created_at": "2026-10-26T03:00:00Z"
}
```

#### 2. CLI Key Management Utilities (`auth` Subcommand)
The CLI provides automated utility subcommands for generating and managing keys:

* **Generate / Rotate Key (`ed-telemetry auth keygen [--force]`):**
  - Uses `secrets.token_hex(16)` to generate a cryptographically strong 32-character token.
  - Automatically writes to the platform-specific `credentials.json` path with strict permissions.
  - Outputs the generated key to `stdout` along with copy-pasteable environment export commands.
* **Inspect Current Key (`ed-telemetry auth show`):**
  - Displays the active key and its storage path.
* **Revoke Key (`ed-telemetry auth revoke`):**
  - Removes the credentials file and reverts to unauthenticated local mode.

#### 3. Complete Credential Resolution Precedence
Whenever `ed-telemetry serve` or client commands boot, the active API key is resolved according to this deterministic hierarchy:

```
1. Explicit CLI Flag:             --api-key <token>
2. Active Environment Variable:   $ED_API_KEY
3. Canonical Credentials File:    ~/.config/ed-telemetry/credentials.json (or %LOCALAPPDATA%)
4. Fallback Default:              None (Unauthenticated local-trusted mode on 127.0.0.1)
```

This ensures downstream packages (`ed-some-package`) running on the same host can automatically discover the credentials file without user intervention, while remote packages across the LAN can ingest `$ED_API_KEY` from their own environment.
