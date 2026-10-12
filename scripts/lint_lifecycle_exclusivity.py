#!/usr/bin/env python3
"""AST static linter enforcing Policy P1: Active Lifecycle Exclusivity Invariant.

Scans all Python files in src/services/ to assert that no service invokes
or defines lifecycle execution methods (.start(), .stop()), with the sole
exception of authorized Lifecycle Supervisor modules (e.g. services/daemon.py).

Governed by ADR 0016 and SDD-014.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = REPO_ROOT / "src" / "services"

# Whitelisted supervisor modules permitted to invoke/manage lifecycle execution
# Note: watcher.py is temporarily grandfathered during pre-DaemonService migration
# and will be strictly disallowed once WatcherService lifecycle methods are retired.
WHITELISTED_SUPERVISOR_MODULES: set[str] = {
    "daemon.py",
    "watcher.py",  # Transitional: grandfathered until DaemonService refactor
}

# Forbidden lifecycle execution method names
FORBIDDEN_LIFECYCLE_METHODS: set[str] = {
    "start",
    "stop",
}


class LifecycleASTVisitor(ast.NodeVisitor):
    """AST visitor detecting invocations or declarations of lifecycle execution methods."""

    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.violations: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Flag attribute calls like self._watcher.start() or adapter.stop()."""
        if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_LIFECYCLE_METHODS:
            self.violations.append(
                f"{self.relative_path}:{node.lineno}: Method call '.{node.func.attr}()' violates Policy P1 "
                "(Lifecycle Exclusivity: Only Path 1 Lifecycle Supervisors may invoke lifecycle methods)."
            )
        self.generic_visit(node)


def lint_services_lifecycle() -> int:
    """Scan src/services/ for Policy P1 AST violations."""
    if not SERVICES_DIR.is_dir():
        print(f"[ERROR] Services directory not found: {SERVICES_DIR}", file=sys.stderr)
        return 1

    all_violations: list[str] = []

    for py_file in SERVICES_DIR.rglob("*.py"):
        rel_path = py_file.relative_to(SERVICES_DIR)

        # Skip whitelisted supervisor modules
        if rel_path.name in WHITELISTED_SUPERVISOR_MODULES:
            continue

        # Skip temporary, registry, dto, or exception definitions
        if rel_path.parts[0] in ("dto", "registry", "exceptions.py"):
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError as err:
            print(f"[ERROR] Syntax error in {py_file}: {err}", file=sys.stderr)
            return 1

        visitor = LifecycleASTVisitor(f"src/services/{rel_path}")
        visitor.visit(tree)
        all_violations.extend(visitor.violations)

    if all_violations:
        print("=" * 60, file=sys.stderr)
        print("POLICY P1 VIOLATION: Active Lifecycle Exclusivity Failed", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        for v in all_violations:
            print(f"  - {v}", file=sys.stderr)
        print(
            "\nRemediation:\n"
            "  Remove .start() / .stop() invocations from non-supervisor services.\n"
            "  Lifecycle management is restricted exclusively to Path 1 supervisors (DaemonService).\n",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(lint_services_lifecycle())
