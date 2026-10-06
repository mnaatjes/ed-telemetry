#!/usr/bin/env python3
"""Hook script ensuring bump-my-version is only executed on the main branch."""

import subprocess
import sys


def verify_main_branch() -> int:
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    except Exception as exc:
        sys.stderr.write(f"ERROR: Failed to detect git branch: {exc}\n")
        return 1

    if branch != "main":
        sys.stderr.write(
            f"\n[BLOCKED] bump-my-version is strictly restricted to the 'main' branch.\n"
            f"Current branch: '{branch}'. Releases must be cut from main.\n\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(verify_main_branch())
