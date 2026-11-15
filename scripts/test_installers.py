"""Verification script for Linux and Windows installer artifacts and service CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Verify Linux/Windows installer scripts, specs, and service CLI wiring."""
    install_sh = REPO_ROOT / "packaging" / "linux" / "install.sh"
    spec_file = REPO_ROOT / "packaging" / "linux" / "ed-telemetry.spec"
    entrypoint = REPO_ROOT / "packaging" / "linux" / "entrypoint.py"
    iss_file = REPO_ROOT / "packaging" / "windows" / "ed-telemetry.iss"

    for path in (install_sh, spec_file, entrypoint, iss_file):
        if not path.exists():
            raise FileNotFoundError(f"Missing packaging artifact: {path}")

    # 1. Linux install.sh syntax check
    subprocess.run(["bash", "-n", str(install_sh)], check=True)

    # 2. Spec references entrypoint.py
    assert "entrypoint.py" in spec_file.read_text(encoding="utf-8")

    # 3. Windows .iss references service install
    assert "service install" in iss_file.read_text(encoding="utf-8")

    # 4. Service CLI subcommand is wired
    subprocess.run([sys.executable, "-m", "ed_telemetry.bootstrap.container", "service", "--help"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
