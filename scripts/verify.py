#!/usr/bin/env python3
"""Cross-platform quality gate verification orchestrator.

Executes Tier 2 checks sequentially:
1. Ruff linting
2. Ruff formatting
3. Mypy static type analysis
4. Import-Linter architectural boundary invariants
5. Pytest test suite
6. CLI composition root smoke test
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

CHECKS: list[tuple[str, list[str]]] = [
    ("Ruff Lint", [sys.executable, "-m", "ruff", "check", "src", "sdk", "tests"]),
    ("Ruff Format Check", [sys.executable, "-m", "ruff", "format", "--check", "src", "sdk", "tests"]),
    ("Mypy Static Typing", [sys.executable, "-m", "mypy"]),
    (
        "Import Linter Boundaries",
        [
            sys.executable,
            "-c",
            "import sys; from importlinter.cli import lint_imports; sys.exit(lint_imports())",
        ],
    ),
    ("Pytest Suite", [sys.executable, "-m", "pytest", "-v"]),
    ("CLI Smoke Test", [sys.executable, "-m", "interfaces"]),
]


def run_checks() -> int:
    """Execute all quality gates sequentially, halting on first failure."""
    print("=" * 60)
    print("Executing Tier 2 Quality Gates")
    print("=" * 60)

    for name, command in CHECKS:
        print(f"\n[RUNNING] {name}...")
        print(f"Command: {' '.join(command)}")
        result = subprocess.run(command, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"\n[FAILED] {name} exited with status {result.returncode}", file=sys.stderr)
            return result.returncode
        print(f"[PASSED] {name}")

    print("\n" + "=" * 60)
    print("All Tier 2 Quality Gates Passed Successfully!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(run_checks())
