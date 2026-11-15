"""Single-instance PID lockfile guard for ed-telemetry."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_lockfile_path() -> Path:
    """Return the OS-standard PID lockfile path."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "ed-telemetry" / "ed-telemetry.pid"


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class SingleInstanceLock:
    """File-based PID lock preventing duplicate ed-telemetry daemon instances."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_lockfile_path()
        self._acquired = False

    def acquire(self) -> bool:
        """Acquire the lockfile. Returns False if another live instance holds it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                existing_pid = int(self.path.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                existing_pid = -1
            if _is_pid_alive(existing_pid) and existing_pid != os.getpid():
                return False
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        self._acquired = True
        return True

    def release(self) -> None:
        """Release the lockfile if held by this process."""
        if self._acquired and self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass
            self._acquired = False
