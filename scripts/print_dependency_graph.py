#!/usr/bin/env python3
"""On-demand AST dependency graph inspector.

Uses grimp to build and display the live import graph across
all packages in the modular monorepo.
"""

from __future__ import annotations

import sys
from collections import defaultdict

try:
    import grimp
except ImportError:
    sys.stderr.write("ERROR: 'grimp' is required. Run 'pip install -e .[dev]'.\n")
    sys.exit(1)

PACKAGES = [
    "ed_domain",
    "ed_watcher",
    "ed_egress",
    "ed_sdk",
    "ed_app",
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
            print(f"  {pkg:<12} ──► [{targets_str}]")
        else:
            print(f"  {pkg:<12} ──► (none / pure isolation)")

    print("\n[Detailed Module-Level Import Pairs]:")
    for src, tgt in direct_imports:
        print(f"  {src} ──► {tgt}")

    print("\n" + "=" * 65)
    print("Boundary Health Check:")
    domain_outgoing = pkg_imports.get("ed_domain", set())
    if not domain_outgoing:
        print("  [OK] Invariant A: 'ed_domain' imports zero sibling packages.")
    else:
        print(f"  [VIOLATION] 'ed_domain' imports: {domain_outgoing}")

    sdk_dependents = {src for src, tgts in pkg_imports.items() if "ed_sdk" in tgts}
    runtime_violators = sdk_dependents - {"ed_sdk"}
    if not runtime_violators:
        print("  [OK] Invariant B: 'ed_sdk' is NOT imported by any runtime package.")
    else:
        print(f"  [VIOLATION] Invariant B breached by: {runtime_violators}")

    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(print_graph())
