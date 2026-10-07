---
title: "Elite Dangerous Journal and Snapshot Filename Specification and Edge Cases"
tags: ["elite-dangerous", "journal", "snapshot", "filenames", "research", "regex"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# Elite Dangerous Journal & Snapshot Filename Specification and Edge Cases

## 1. Executive Summary

This document establishes the governing file naming rules, historical variations, build-specific suffixes, and operational edge-cases for telemetry files produced by Frontier Developments (FDev) *Elite Dangerous*. The objective is to inform robust file discovery and watching strategies in `ed-telemetry` without hardcoding brittle assumptions.

---

## 2. Journal File Naming Specification

Elite Dangerous writes chronological gameplay events as line-delimited JSON (JSONL) into append-only log files. The filename format is:

$$\text{Prefix} + \text{BuildSuffix} + \text{.} + \text{Timestamp} + \text{.} + \text{Part} + \text{.log}$$

### 2.1 Component Breakdown

1. **Prefix**: Fixed string `Journal`.
2. **Build Suffix (`BuildSuffix`)**:
   - Production / Live: Empty string `""`.
   - Public Alpha: `Alpha` (e.g. Odyssey pre-release tests: `JournalAlpha...`).
   - Public Beta: `Beta` (e.g. Major feature beta tests: `JournalBeta...`).
3. **Delimiter**: Literal dot (`.`).
4. **Timestamp (`Timestamp`)**:
   - **Modern Odyssey Era (Update 11+ / Live 4.0, April 2022 to present)**:
     - ISO 8601-like format: `YYYY-MM-DDTHHMMSS` (e.g., `2026-10-07T032501`).
     - Exactly 15 characters (`\d{4}-\d{2}-\d{2}T\d{6}`).
   - **Legacy Era (Horizons 3.x, Legacy 3.8, Odyssey pre-Update 11)**:
     - Compact format: `YYMMDDHHMMSS` (e.g., `220315152335`).
     - Exactly 12 numeric digits (`\d{12}`).
5. **Part Number (`Part`)**:
   - Two-digit counter: `01`, `02`, `03` (`\d{2}`).
   - *Split Condition*: Initiated as `01` upon game client startup. If a single play session exceeds file size limits (historically around ~500 MB) or encounters an internal game engine rotation boundary without client termination, the game closes the active file and opens a successor with an incremented part number (`02.log`, `03.log`) retaining the original start timestamp or assigning the current rotation timestamp.
   - *Edge Case*: Rare historical Horizons builds or third-party simulators omit or pad parts; parser must accept `\d{2}` minimum and optional part variants.
6. **File Extension**: Fixed string `.log`.

---

## 3. Snapshot (Discrete State) Filename Specification

Unlike the append-only rolling journal files, snapshot files represent point-in-time state tables. They are written to the exact same directory as the player journal (`Saved Games/Frontier Developments/Elite Dangerous/`).

### 3.1 Inventory of Snapshot Files

| Filename | Purpose / Context | Write Timing | Mutation Pattern |
| :--- | :--- | :--- | :--- |
| `Status.json` | Cockpit HUD, landing gear, hardpoints, pips, fuel, legal status | ~1.0 Hz periodic or on cockpit state transition | Overwrite (truncate in place) |
| `Market.json` | Station commodity market price/demand catalog | Opening station Commodities screen | Overwrite (truncate in place) |
| `Outfitting.json` | Station module outfitting inventory and prices | Opening station Outfitting screen | Overwrite (truncate in place) |
| `Shipyard.json` | Station shipyard ships available for sale | Opening station Shipyard screen | Overwrite (truncate in place) |
| `ModulesInfo.json` | Current ship module loadout, power priorities, health | Cockpit startup, module switching, power tuning | Overwrite (truncate in place) |
| `Cargo.json` | Ship cargo inventory manifest | Game startup, cargo scooping, jettison, trading | Overwrite (truncate in place) |
| `Backpack.json` | Odyssey on-foot inventory (consumables, components, assets) | Disembarking, looting, resupply terminal interaction | Overwrite (truncate in place) |
| `NavRoute.json` | Active multi-hop galaxy map navigation route | Plotting route in Galaxy Map or clearing route | Overwrite (truncate in place) |
| `FCMaterials.json` | Fleet Carrier Bartender material inventory and orders | Interacting with Fleet Carrier bar | Overwrite (truncate in place) |

---

## 4. Edge-Cases, Discrepancies, and Variances

### 4.1 Non-Atomic Truncation Races (Snapshot Files)
- **Mechanism**: The Windows game client opens snapshot files with truncate flags (`w` / `O_TRUNC`) and writes new content.
- **Race Condition**: External watchers (like inotify, ReadDirectoryChangesW, or polling loops) often trigger an `on_modified` event when the file size becomes 0 bytes before the write buffer flushes.
- **Remediation**:
  1. Guard against empty reads: Do not attempt `json.loads()` if file size is 0 or buffer is empty.
  2. Retry backoff: If a decode error occurs on snapshot reads, apply exponential backoff (e.g. 10ms–50ms, up to 3 retries) before declaring corruption.

### 4.2 Shared Journal Directory Across Live and Beta Builds
- Beta and live clients write to the same directory path (`.../Frontier Developments/Elite Dangerous/`).
- While journals differentiate via prefix (`Journal.` vs `JournalBeta.`), snapshot files (e.g. `Status.json`) do **not** use build prefixes. `Status.json` is shared and can be overwritten by whichever client is currently executing.
- **Remediation**: Correlation must be maintained with the active journal session timestamp (`session_start`) to ignore stale snapshot updates from older sessions.

### 4.3 Filesystem Casing and Cross-Platform Normalization
- On Windows NTFS, case is preserved but insensitive (`status.json` vs `Status.json`).
- Under Linux (Wine/Proton), case sensitivity is enforced by the native Linux filesystem. The game client running in Wine creates PascalCase filenames (`Status.json`, `Cargo.json`), but user scripts or manual symlinks might introduce lowercase variants.
- **Rule**: Filename matching should be case-insensitive for discovery queries, but canonical PascalCase must be preferred when creating or referencing paths.

### 4.4 Journal Rollover & Re-identification
- When part splitting occurs (`01.log` -> `02.log`), the timestamp component may either remain unchanged or advance.
- Watchers must not solely rely on sorting timestamps: sorting must consider `(timestamp, part_number)` or filesystem creation timestamp (`getctime`).

---

## 5. Governing Regex & Recognition Rules

### 5.1 Python Canonical Regex for Journal Recognition

```python
import re

# Comprehensive pattern supporting:
# - Standard Live: Journal.2026-10-07T032501.01.log
# - Legacy:        Journal.220315152335.01.log
# - Test Builds:   JournalAlpha... / JournalBeta...
JOURNAL_FILE_REGEX = re.compile(
    r"^Journal(?P<build>Alpha|Beta)?"
    r"\.(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{6}|\d{12})"
    r"\.(?P<part>\d{2})"
    r"\.log$",
    re.IGNORECASE,
)
```

### 5.2 Snapshot File Membership Set

```python
SNAPSHOT_FILES = frozenset(
    {
        "Status.json",
        "Market.json",
        "Outfitting.json",
        "Shipyard.json",
        "ModulesInfo.json",
        "Cargo.json",
        "Backpack.json",
        "NavRoute.json",
        "FCMaterials.json",
    }
)
```
