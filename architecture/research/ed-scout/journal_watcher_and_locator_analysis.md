---
title: "Repository Research: ed-scout Journal Watcher & Path Locator Analysis"
tags: ["research", "reference", "ed-scout", "watchdog", "file-watching", "saved-games"]
created_at: "2026-10-08"
last_updated_at: "2026-10-08"
---

# Repository Research: ed-scout Journal Watcher & Path Locator Analysis

## 1. Diagnostic: Implementation Breakdown

`ed-scout` isolates its file-monitoring mechanisms into three modules:
1. `SavedGamesLocator.py`: Resolves the absolute directory containing journals.
2. `JournalWatcher` (in `JournalInterface.py`): Subscribes to filesystem notifications using the Python `watchdog` library.
3. `JournalChangeProcessor` (in `JournalInterface.py`): Reads byte deltas from modified journals and converts lines into parsed event dictionaries.

## 2. Theory: Saved Games Resolution (`SavedGamesLocator.py`)

`SavedGamesLocator.py` implements platform-specific path heuristics:

```python
def get_saved_games_path():
    save_game_root = None
    osname = platform.system()
    if osname == "Windows":
        sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        downloads_guid = "{4C5C32FF-BB9D-43b0-B5B4-2D72E54EAAA4}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            location = winreg.QueryValueEx(key, downloads_guid)[0]
        save_game_root = location
    elif osname == "Linux":
        save_game_root = os.path.join(
            os.path.expanduser("~"),
            ".local",
            "share",
            "Steam",
            "steamapps",
            "compatdata",
            "359320",
            "pfx",
            "drive_c",
            "users",
            "steamuser",
            "Saved Games",
        )
    return os.path.join(save_game_root, "Frontier Developments", "Elite Dangerous")
```

### Analysis of Locator Design
* **Windows Mechanism:** Relies on querying `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders` using GUID `{4C5C32FF-BB9D-43b0-B5B4-2D72E54EAAA4}` (which actually resolves the `SavedGames` known folder).
* **Linux / Proton Mechanism:** Hardcodes Steam App ID `359320` (Elite Dangerous) under the default user path `~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games`.
* **Shortcomings for `ed-telemetry`:**
  1. Does not account for custom Steam library folders (e.g., secondary NVMe drives or `/mnt/games`).
  2. Does not support non-Steam standalone Frontier Launchers or Flatpak Steam installations (`~/.var/app/com.valvesoftware.Steam/...`).
  3. Validates ADR 0007's requirement for a configurable, multi-stage `PathDiscoverer` fallback chain.

## 3. Analysis: File Watching Architecture (`JournalInterface.py`)

### The Event Handler & Observer
`JournalWatcher` wraps `watchdog.observers.Observer` (inotify on Linux, ReadDirectoryChangesW on Windows) and provides an optional fallback to `watchdog.observers.polling.PollingObserver(0.25)`:

```python
if self.force_polling:
    self.observer = PollingObserver(0.25)
else:
    self.observer = Observer()
self.observer.schedule(self.event_handler, self.journal_path, recursive=False)
```

### Delta Reading via Negative Seek (`f.seek(-size_diff, os.SEEK_END)`)

To read new lines appended to the journal, `JournalChangeProcessor.process_journal_change` performs:

```python
new_size = os.stat(changed_file).st_size
if new_size > 0:
    size_diff = new_size - self.journal_size
    if size_diff > 0:
        with open(changed_file, "rb") as f:
            f.seek(-size_diff, os.SEEK_END)
            new_data = f.read()
```

### Flaws & Vulnerabilities in ed-scout's Delta Read Logic

1. **Race Condition with Concurrent Writes:**
   `f.seek(-size_diff, os.SEEK_END)` is non-atomic. If the game engine appends additional bytes between `os.stat()` and `open()`, `os.SEEK_END - size_diff` will calculate an offset starting *ahead* of the previous read position, silently skipping events!
2. **Crash on File Truncation / Rotation:**
   If a log rotates or truncates such that `new_size < self.journal_size`, `size_diff` becomes negative. Seeking `-(-diff)` bytes past `SEEK_END` raises `OSError: [Errno 22] Invalid argument`.
3. **Line Boundary Corruption:**
   `as_ascii.split("\r\n")` assumes lines end strictly with Windows CRLF. If a partial line write occurs mid-flush, decoding and splitting drops or corrupts JSON parsing:
   ```python
   except json.decoder.JSONDecodeError as e:
       logger.exception(e)
   ```
   When `JSONDecodeError` triggers, `self.journal_size` is **not updated**, but on the subsequent write, `size_diff` seeks from `SEEK_END` again, potentially duplicating or dropping the corrupted buffer.

## 4. Remediation: Linux Watchdog Flaw & FileSystemUpdatePrompter

In `test_JournalWatcher.py`:
```python
@pytest.mark.skip(reason="unreliable on linux")
def test_extract_new_entries_from_file(self): ...
```
The test suite explicitly disables inotify-based journal tests on Linux because standard `watchdog.observers.Observer` fails to reliably capture fast sequential file modifications across Proton virtual wine prefixes.

To combat this in production, `ed-scout` authors added `FileSystemUpdatePrompter.py`—a background daemon thread that runs an endless loop executing `os.stat()` every 100ms (`sleep(0.1)`):

```python
class FileSystemUpdatePrompter:
    def file_check(self):
        while True:
            new_size = os.stat(self.path_to_query).st_size
            ...
            sleep(0.1)
```

### Validation of ADRs 0008 & 0009
This finding provides empirical evidence justifying `ed-telemetry`'s architecture:
* ADR 0008 abandons negative `SEEK_END` arithmetic in favor of **monotonic byte offset tracking** (`f.seek(last_offset, os.SEEK_SET)`).
* ADR 0009 avoids fragile standalone inotify observers by specifying a **hybrid reactor** combining OS notifications with a disciplined 0.5s/1.0s timeout ticker loop.
