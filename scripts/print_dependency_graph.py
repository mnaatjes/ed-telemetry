#!/usr/bin/env python3
"""On-demand AST dependency graph inspector.

Uses grimp to build and display the live import graph across
all packages in the pure hexagonal topology and satellite SDK.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    import grimp
except ImportError:
    sys.stderr.write("ERROR: 'grimp' is required. Run 'pip install -e .[dev]'.\n")
    sys.exit(1)

PACKAGES = [
    "domain",
    "services",
    "infrastructure",
    "interfaces",
    "sdk",
]


def print_graph() -> int:
    print("=" * 65)
    print("Live AST Dependency & Boundary Graph (grimp)")
    print("=" * 65)

    graph = grimp.build_graph(*PACKAGES)

    # Collect all direct imports
    direct_imports: list[tuple[str, str]] = []
    pkg_imports: dict[str, set[str]] = defaultdict(set)

    for mod in sorted(graph.modules):
        imported_modules = graph.find_modules_directly_imported_by(mod)
        src_top = mod.split(".")[0]
        for imported in sorted(imported_modules):
            direct_imports.append((mod, imported))
            tgt_top = imported.split(".")[0]
            if src_top != tgt_top:
                pkg_imports[src_top].add(tgt_top)

    print("\n[Package Cross-Boundary Imports]:")
    for pkg in PACKAGES:
        targets = sorted(pkg_imports.get(pkg, set()))
        if targets:
            targets_str = ", ".join(targets)
            print(f"  {pkg:<15} ──► [{targets_str}]")
        else:
            print(f"  {pkg:<15} ──► (none / pure isolation)")

    print("\n[Detailed Module-Level Import Pairs]:")
    for src, tgt in direct_imports:
        print(f"  {src} ──► {tgt}")

    print("\n" + "=" * 65)
    print("Boundary Health Check:")
    domain_outgoing = pkg_imports.get("domain", set())
    if not domain_outgoing:
        print("  [OK] Invariant A: 'domain' imports zero sibling packages.")
    else:
        print(f"  [VIOLATION] 'domain' imports: {domain_outgoing}")

    sdk_dependents = {src for src, tgts in pkg_imports.items() if "sdk" in tgts}
    runtime_violators = sdk_dependents - {"sdk"}
    if not runtime_violators:
        print("  [OK] Invariant B: 'sdk' is NOT imported by any production package.")
    else:
        print(f"  [VIOLATION] Invariant B breached by: {runtime_violators}")

    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(print_graph())
