---
title: "Reference: ed_watcher OS Path Discovery API"
tags: ["reference", "watcher", "path-discovery", "api"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# Reference: ed_watcher OS Path Discovery API

This reference describes the classes, protocols, models, and exceptions provided by the `ed_watcher.discovery` subsystem for resolving Elite Dangerous journal directories across supported operating systems.

---

## 1. Primary Class: `PathDiscoverer`

```python
class PathDiscoverer:
    def __init__(
        self,
        strategy: PathDiscoveryStrategy | None = None,
        platform_type: SupportedPlatform | None = None,
    ) -> None: ...
```

The central coordinator responsible for resolving candidate paths. It evaluates discovery sources in strict precedence:
1. Explicit parameter override passed to `discover_journal_directory()`.
2. Environment variable override (`$ED_JOURNAL_DIR`).
3. Host platform automated strategy (`WindowsPathStrategy` on Windows, `LinuxProtonPathStrategy` on Linux).

### Constructor Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `strategy` | `PathDiscoveryStrategy \| None` | `None` | Optional custom or mocked discovery strategy. If omitted, selected automatically based on `platform_type`. |
| `platform_type` | `SupportedPlatform \| None` | `None` | Host platform category. If omitted, detected via `SupportedPlatform.from_current_platform()`. |

---

## 2. Methods

### `discover_journal_directory()`

```python
def discover_journal_directory(
    self,
    override_path: Path | str | None = None,
) -> DiscoveryResult: ...
```

Executes the discovery funnel and returns the canonical journal directory.

#### Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `override_path` | `Path \| str \| None` | `None` | Optional explicit path provided by the caller. Bypasses automated platform heuristics. |

#### Returns
* **`DiscoveryResult`**: Immutable dataclass containing the resolved canonical path and discovery source identifier.

#### Exceptions Raised

| Exception | Condition |
| :--- | :--- |
| **`InvalidPathOverrideError`** | Raised when an explicit parameter or `$ED_JOURNAL_DIR` override does not exist or is not a readable directory. |
| **`UnsupportedPlatformError`** | Raised when running on an operating system without an automated strategy (e.g., macOS, BSD). |
| **`JournalPathNotFoundError`** | Raised when automated platform strategies exhaust all candidate locations without encountering a valid journal folder. |

---

## 3. Data Models

### `DiscoveryResult`

```python
@dataclass(frozen=True)
class DiscoveryResult:
    resolved_path: Path
    discovery_source: str
```

* **`resolved_path` (`pathlib.Path`)**: Absolute, canonical path to the discovered journal directory.
* **`discovery_source` (`str`)**: Identifier indicating how the directory was resolved:
  - `"parameter_override"`: From `override_path` parameter.
  - `"env_override"`: From `$ED_JOURNAL_DIR` environment variable.
  - `"platform_win32"`: From Windows Known Folders or Registry.
  - `"platform_linux"`: From Linux Steam / Proton / Flatpak heuristics.

### `SupportedPlatform`

```python
class SupportedPlatform(StrEnum):
    WINDOWS = "win32"
    LINUX = "linux"
    UNSUPPORTED = "unsupported"
```

Enumerates recognized host execution platforms. Use `SupportedPlatform.from_current_platform()` to query the active environment.

---

## 4. Exception Hierarchy

All discovery exceptions derive from `WatcherError`:

```text
WatcherError (Exception)
└── PathDiscoveryError
    ├── UnsupportedPlatformError
    │   └── platform_name: str
    ├── InvalidPathOverrideError
    │   ├── target_path: Path
    │   ├── source: str ("parameter" | "environment")
    │   └── reason: str ("does_not_exist" | "not_a_directory")
    └── JournalPathNotFoundError
        ├── inspected_paths: tuple[Path, ...]
        └── platform_name: str
```

---

## 5. Usage Examples

### Automated Platform Detection
```python
from ed_watcher import PathDiscoverer, DiscoveryResult, PathDiscoveryError

discoverer = PathDiscoverer()

try:
    result: DiscoveryResult = discoverer.discover_journal_directory()
    print(f"Discovered path: {result.resolved_path}")
    print(f"Source: {result.discovery_source}")
except PathDiscoveryError as err:
    print(f"Could not locate journal directory: {err}")
```

### Parameter Override
```python
from pathlib import Path
from ed_watcher import PathDiscoverer, InvalidPathOverrideError

discoverer = PathDiscoverer()
custom_path = Path("/mnt/games/EliteDangerous/SavedGames")

try:
    result = discoverer.discover_journal_directory(override_path=custom_path)
    print(f"Using override: {result.resolved_path}")
except InvalidPathOverrideError as err:
    print(f"Invalid path ({err.reason}): {err.target_path}")
```
