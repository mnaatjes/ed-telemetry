---
title: "Elite Dangerous Target Files Software & System Metadata Research"
tags: ["elite-dangerous", "journal", "snapshot", "metadata", "research", "architecture"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# Elite Dangerous Target Files: Software & System Metadata Research

## 1. Executive Summary

This research investigates the non-gameplay metadata embedded within Frontier Developments (FDev) *Elite Dangerous* telemetry files. Specifically, this analysis focuses on metadata properties associated with:
1. **The Game Software & Build Context** (engine version, build hashes, language/locale, runtime client flags).
2. **The Operating System & Filesystem Artifacts** (file encoding, stream characteristics, file descriptors, part partitioning, atomic write semantics).
3. **The Session & Player Identity Envelope** (account identifiers, session timestamps, part sequence counters).

This research informs how `ed-telemetry` ingests, correlates, and validates target files independent of gameplay mechanics (flight physics, combat stats, trading numbers).

---

## 2. File-Level & Operating System Properties

### 2.1 File Encoding and Text Stream Format
* **Character Encoding**: Strictly UTF-8 without Byte Order Mark (BOM).
* **Line Delimiter**: Standard Windows CRLF (`\r\n`) or Unix LF (`\n`). Parsers must strip trailing whitespace (`\r`, `\n`) when processing lines.
* **Stream Serialization**:
  - **Journal Files**: Line-delimited JSON (JSONL). Each record is an isolated, self-contained single-line JSON document terminated by a newline.
  - **Snapshot Files**: Single JSON document containing one top-level dictionary (`Object`).

### 2.2 Filesystem Lifecycle & Access Semantics
* **Journal Logs (`Journal.*.log`)**:
  - Opened by the game engine with append mode (`FILE_APPEND_DATA` / `a`).
  - Flush frequency: Written on event emission; internal game buffers flush immediately or within milliseconds.
  - File locking: Opened with shared read permissions (`FILE_SHARE_READ`), permitting external read access while the game writes.
* **Snapshot Files (`*.json`)**:
  - Opened with truncate-and-write semantics (`O_TRUNC` / `w`).
  - Write behavior is **non-atomic**: FDev truncates `<file>.json` to 0 bytes before writing new JSON content.
  - File locks: Ephemeral shared read during flush.

---

## 3. Game-Software & Session Metadata in Journal Files

Every journal file contains non-gameplay metadata records that declare the software environment, file lineage, and account ownership.

### 3.1 The `Fileheader` Record (Initial Event)
The very first record written to any journal file is strictly the `Fileheader`. It establishes the operational identity of the file and the engine that generated it.

```json
{
  "timestamp": "2026-10-07T03:25:01Z",
  "event": "Fileheader",
  "part": 1,
  "language": "English\\UK",
  "Odyssey": true,
  "gameversion": "4.0.0.1804",
  "build": "r308304 "
}
```

#### Metadata Attributes Defined in `Fileheader`:
| Field Name | Type | Value Domain | Metadata Purpose |
| :--- | :--- | :--- | :--- |
| `timestamp` | `string` | ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) | Creation timestamp of the physical log file. |
| `event` | `string` | Literal `"Fileheader"` | Identifies the file preamble record. |
| `part` | `integer` | $\ge 1$ (starts at `1`) | Sequence part number for long sessions. Matches part in filename. |
| `language` | `string` | e.g. `"English\\UK"`, `"French\\FR"`, `"German\\DE"` | Installed client localization dictionary in use. |
| `odyssey` / `Odyssey` | `boolean` | `true` or `false` | Distinguishes 4.0 Odyssey runtime from Horizons 3.8/4.0 runtime. (Note: case varies between builds; check case-insensitively). |
| `gameversion` | `string` | Semantic/dotted version (e.g. `"4.0.0.1804"`, `"3.8"`) | FDev client executable release version. |
| `build` | `string` | Build revision tag (e.g. `"r308304 "`) | Internal FDev source control commit/build hash. |

### 3.2 The `LoadGame` Metadata Duplication
When a player loads into an active game session from the main menu, `LoadGame` is emitted. In Odyssey Release Update 5+, FDev redundantly embeds:
- `language`: Client language.
- `gameversion`: Client version.
- `build`: Build revision.
- `Odyssey`: Boolean flag.

This allows stream consumers that missed the `Fileheader` (e.g. mid-session startup) to re-acquire the software build context.

### 3.3 Account Identification: The `Commander` Record
Emitted upon entering the game universe to identify the account context:
```json
{
  "timestamp": "2026-10-07T03:25:05Z",
  "event": "Commander",
  "FID": "F12345678",
  "Name": "Surly_Badger"
}
```
* **`FID` (Frontier ID)**: Permanent alphanumeric account identifier assigned by Frontier Developments. Unique per customer account; remains immutable even if the player changes their Commander display name or resets save files.
* **`Name`**: Commander display name.

### 3.4 Session Lifecycle Markers: `Shutdown`
```json
{
  "timestamp": "2026-10-07T05:12:30Z",
  "event": "Shutdown"
}
```
* Emitted upon clean exit of the game client.
* Absence of `Shutdown` indicates either an active ongoing session, a client crash, or an abnormal termination (kill process/power loss).

---

## 4. Metadata in Snapshot Files

Unlike the main journal, snapshot files are dedicated JSON state representations. However, they consistently embed session and location envelope metadata headers.

### 4.1 Common Snapshot Envelope Headers
All snapshot files share a baseline metadata header:

| Header Attribute | Type | Present In | Description |
| :--- | :--- | :--- | :--- |
| `timestamp` | `string` | All snapshot files | ISO 8601 UTC timestamp of the snapshot generation. |
| `event` | `string` | All snapshot files | Matches the snapshot category (e.g. `"Status"`, `"Market"`, `"Cargo"`). |
| `MarketID` | `integer` / `null` | `Market.json`, `Outfitting.json`, `Shipyard.json`, `Cargo.json`, `Status.json` | FDev 64-bit persistent ID of the station, carrier, or outpost. |
| `StationName` | `string` / `null` | `Market.json`, `Outfitting.json`, `Shipyard.json` | Name of the starport generating the snapshot. |
| `StarSystem` | `string` / `null` | `Market.json`, `Outfitting.json`, `Shipyard.json` | Star system where the market was queried. |
| `SystemAddress` | `integer` / `null` | `Market.json`, `NavRoute.json`, `Status.json` | 64-bit procedural galaxy address of the star system. |
| `Horizons` | `boolean` | `Market.json`, `Outfitting.json`, `Shipyard.json` | Flag indicating whether Horizons DLC content is enabled for stock. |
| `Odyssey` | `boolean` | `Market.json`, `Outfitting.json`, `Shipyard.json` | Flag indicating whether Odyssey DLC content is enabled. |

### 4.2 `Status.json` Specific Metadata Flags
In addition to general timestamps, `Status.json` contains cockpit state bitfields:
* `Flags`: 32-bit bitfield integer representing vehicle status flags (Docked, Landed, Landing Gear, Supercruise, Hardpoints, Lights, Cargo Scoop, Silent Running, Fuel Scoop, etc.).
* `Flags2`: 32-bit bitfield integer representing Odyssey on-foot flags (On Foot, In Taxi, In Multicrew, On Foot in Station, On Foot on Planet, Aim Down Sights, Low Oxygen, Cold/Heat, Glide Mode).

---

## 5. Architectural Implications for `ed-telemetry`

1. **System Session Context**:
   The engine's `ed_watcher` should extract `(FID, gameversion, build, Odyssey)` upon encountering `Fileheader` / `Commander` and publish this as a domain session header (`SessionContext`).
2. **Snapshot Freshness & Session Reconciliation**:
   Snapshot files (`Status.json`, `Cargo.json`, etc.) do **not** record the file part number or `FID`. Correlation with the active session must be verified by comparing `snapshot.timestamp >= session.start_timestamp`.
3. **Resilience to Incomplete Flushes**:
   Watchers on `Status.json` and other snapshot files must treat empty buffers (`len(data) == 0`) and transient JSON decoding errors as in-progress writes rather than catastrophic errors, retrying gracefully.
