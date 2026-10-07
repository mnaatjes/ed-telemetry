---
title: "Platform Research Governance and Knowledge Base"
tags: ["architecture", "research", "governance", "index"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# Platform Research Governance and Knowledge Base

This directory serves as the engineering ledger and single source of truth for empirical platform research governing `ed-telemetry`. It captures empirical facts, OS-level discovery mechanics, filesystem contracts, and third-party protocol behaviors verified across supported deployment environments.

---

## 1. Principles & Quality Invariants

1. **Empirical Factuality:** Every research finding must be verified against actual game installations, real operating system environments (native Windows, Linux Proton / Steam Deck / Wine), or official frontier/community API specifications.
2. **Immutable Traceability:** Findings document observable behaviors and contracts at specific dates and game/client versions.
3. **Zero Repository Bloat:** Never commit multi-megabyte log dumps or `.zip` binary archives to this repository. Research documents must contain structured markdown, tables, and code snippets. Example data fixtures must strictly adhere to the < 20 KB limit defined in [ADR 0004](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0004_os_path_discovery_and_filesystem_research_framework.md).
4. **Separation from Product Logic:** Research documents record "how the external system behaves", not "how `ed-telemetry` implements internal features". Implementation decisions belong in `architecture/adr/` or `architecture/designs/`.

---

## 2. Research Catalog

| Document | Topic | Target OS / Environment | Status | Last Verified |
| :--- | :--- | :--- | :---: | :---: |
| [0001: OS Targets, Journal Filesystem Catalog, and Ingestion Mechanics](0001_os_targets_and_filesystem_catalog.md) | OS targets, filesystem paths, journal taxonomy, file locks, encoding | Windows 10/11, Linux Proton, Steam Deck, Wine | **Active** | 2026-10-07 |
