---
title: "EDMarketConnector Journal and Snapshot Processing Analysis"
tags: ["edmarketconnector", "journal", "snapshot", "jsonl", "analysis"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# EDMarketConnector Journal & Snapshot Processing Analysis

## 1. Executive Summary

This document analyzes how [EDMarketConnector](https://github.com/mnaatjes/EDMarketConnector) discovers, tracks, parses, and interacts with Frontier Developments (FDev) Elite Dangerous telemetry files:
1. **Journal Files (`Journal.*.log`)**: Incremental append-only JSONL files containing game lifecycle events.
2. **Snapshot / State Files (`*.json`)**: Discrete overwrite-on-change JSON files produced by the game client (`Status.json`, `Market.json`, `Outfitting.json`, `Shipyard.json`, `NavRoute.json`, `ModulesInfo.json`, `Cargo.json`, `Backpack.json`, `FCMaterials.json`).

---

## 2. Journal File Identification & Tracking

### 2.1 File Naming & Regex Matching
In [monitor.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/monitor.py#L64):
```python
_RE_LOGFILE = re.compile(
    r"^Journal(Alpha|Beta)?\.[0-9]{2,4}(-)?[0-9]{2}(-)?[0-9]{2}(T)?[0-9]{2}[0-9]{2}[0-9]{2}"
    r"(\.[0-9]{2})?\.log$"
)
```
- Matches both Horizons formats (`Journal.YYMMDDHHMMSS.NN.log`) and Odyssey formats (`Journal.YYYY-MM-DDTHHMMSS.NN.log`).
- Handles optional `Alpha` and `Beta` suffixes.

### 2.2 Initial File Discovery
In [monitor.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/monitor.py#L265-L283) (`EDLogs.journal_newest_filename`):
- Iterates directory entries via `os.listdir(journals_dir)`.
- Filters using `_RE_LOGFILE.search()`.
- Picks the newest file using `max(journal_files, key=os.path.getctime)`.

### 2.3 Real-time Monitoring & File Rotation
- Uses `watchdog.observers.Observer` with `FileSystemEventHandler` ([monitor.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/monitor.py#L56)).
- Listens to `on_created` events: if a newly created file matches `_RE_LOGFILE`, updates `self.logfile`.
- In Linux/Wine environments where filesystem event notifications may be unreliable, supports configurable periodic polling fallback.
- The worker thread loops on file descriptor handle, tracking file position via `loghandle.tell()` and polling for EOF advances or log file rotation.

---

## 3. Journal Content & JSONL Parsing

### 3.1 JSONL Consumption
- **Yes, EDMarketConnector explicitly parses JSONL.**
- In [monitor.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/monitor.py#L375-L387) and `EDLogs.parse_entry`:
  1. Opens the journal file in binary mode (`open(logfile, 'rb', 0)`).
  2. Iterates line-by-line (`for line in loghandle:`).
  3. Deserializes each line using standard `json.loads(line)` ([monitor.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/monitor.py#L560)).
  4. Inspects `entry['event']` and dispatching internally to mutate the in-memory `monitor.state` dictionary.
  5. Queues parsed dictionaries onto an internal event queue (`self.event_queue.put(...)`) for plugin consumption.

### 3.2 Historical Catch-Up vs. Live Processing
- On startup, seeks through the entire active journal from offset 0 (`self.catching_up = True`).
- Rebuilds session state (Commander name, current system, docked state, ship loadout, carrier market ID).
- Once end-of-file is reached, switches `self.catching_up = False` and begins streaming live events.

---

## 4. Snapshot File Identification & Processing

Elite Dangerous writes several discrete JSON state files into the same journal directory. EDMarketConnector processes them via two distinct mechanisms:

### 4.1 Periodic Polling & Watchdog (`Status.json`)
Managed in [dashboard.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/dashboard.py):
- Dedicated `Dashboard` class with its own `watchdog` handler and 1-second fallback poll timer (`self.root.after(1000, self.process_periodic)`).
- Targets `<journaldir>/Status.json`.
- **Handling Write Race Conditions:**
  ```python
  with open(status_json_path, "rb") as h:
      data = h.read().strip()
      if data:  # Can be empty if polling while the file is being re-written
          entry = json.loads(data)
  ```
  FDev rewrites `Status.json` by truncating and rewriting in place, causing temporary empty reads (handled by checking `if data:` and catching `JSONDecodeError`).

### 4.2 Event-Driven Snapshot Ingestion (`*.json`)
Secondary snapshot files are read reactively in [monitor.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/monitor.py) and [plugins/eddn.py](file:///home/michael/src/github.com/mnaatjes/EDMarketConnector/plugins/eddn.py) when triggered by specific Journal JSONL events:

| Snapshot File | Triggering Journal Event | Purpose / Target Consumer | Location in EDMC |
| :--- | :--- | :--- | :--- |
| `Cargo.json` | `Cargo` | Ingests full cargo manifest | `monitor.py:1115` |
| `Backpack.json` | `BackpackChange`, `Resupply` | Ingests Odyssey on-foot inventory | `monitor.py:1211` |
| `NavRoute.json` | `NavRoute`, `NavRouteClear` | Multi-hop route plotting data | `monitor.py:2427` |
| `ModulesInfo.json` | `ModuleInfo` | Power grid & module priority tracking | `monitor.py:1587` |
| `FCMaterials.json` | `FCMaterials` | Fleet Carrier Bartender inventory | `monitor.py:2453` |
| `Market.json` | `Market` event | Commodity market prices (sent to EDDN) | `plugins/eddn.py:2501` |
| `Outfitting.json` | `Outfitting` event | Station outfitting stock (sent to EDDN) | `plugins/eddn.py:2501` |
| `Shipyard.json` | `Shipyard` event | Station shipyard stock (sent to EDDN) | `plugins/eddn.py:2501` |

---

## 5. Writes and Re-writes Analysis

### 5.1 Game Client Write Patterns (Observed by EDMC)
- **Journal Files:** Append-only. FDev opens the journal file with append mode and flushes newline-terminated JSON entries.
- **Snapshot Files:** Non-atomic truncating overwrites. FDev opens `<File>.json`, truncates, and writes new content. This produces transient 0-byte window reads in external tools, requiring retry/guard handling.

### 5.2 EDMarketConnector File Modification Behavior
- **Does EDMarketConnector write or re-write game journal or snapshot files?**
  - **NO.** EDMarketConnector treats all FDev journal files and snapshot files as **strictly read-only**.
- All write operations across EDMarketConnector are confined to:
  1. Internal user configuration (`config.ini` / registry).
  2. Diagnostic logs (`EDMarketConnector.log`).
  3. User export requests (e.g. ship loadout exports to Coriolis/EDShipyard `.txt`/`.json` or commodity price CSV exports).
