"""Unit tests for SingleInstanceLock."""

from __future__ import annotations

import os
from pathlib import Path

from ed_telemetry.bootstrap.lockfile import SingleInstanceLock


def test_lockfile_acquire_and_release(tmp_path: Path) -> None:
    lock_path = tmp_path / "ed-telemetry.pid"
    lock = SingleInstanceLock(lock_path)

    assert lock.acquire() is True
    assert lock_path.exists()
    assert lock_path.read_text(encoding="utf-8").strip() == str(os.getpid())

    lock.release()
    assert not lock_path.exists()


def test_lockfile_replaces_stale_pid(tmp_path: Path) -> None:
    lock_path = tmp_path / "ed-telemetry.pid"
    lock_path.write_text("99999999", encoding="utf-8")

    lock = SingleInstanceLock(lock_path)
    assert lock.acquire() is True
    lock.release()
