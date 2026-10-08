---
title: "Repository Research: elite-api-docs Overview & Provenance"
tags: ["research", "reference", "elite-api-docs", "frontier-api"]
created_at: "2026-10-08"
last_updated_at: "2026-10-08"
---

# Repository Research: elite-api-docs Overview & Provenance

## 1. Diagnostic: Purpose & Scope

The repository `Lombra/elite-api-docs` (`/home/michael/src/github.com/Lombra/elite-api-docs`) serves as the community-maintained Markdown conversion of Frontier Developments' official *Elite Dangerous Player Journal Manual*.

Historically distributed by Frontier Developments (FDev) as standalone `.doc` / `.pdf` releases on official forums, `elite-api-docs` renders this specification into an accessible web resource powered by VitePress and ReadTheDocs (`.readthedocs.yaml`).

### Repository Metadata

* **Upstream Source:** Frontier Developments Player Journal Specification.
* **Maintainer:** Lombra (with community PR contributions, e.g., Stumpii).
* **Latest Documented Version:** Journal Specification Version 37 (covering Odyssey through Update 14, May 2023) with incremental additions extending into 2024/2026 (e.g., Supercruise Overdrive SCO bitflags, Supercruise Assist active flags).
* **Total Documentation Volume:** 15 documentation modules totaling 7,495 lines of Markdown.
* **Tooling:** Node.js (`package.json`, VitePress, `build.js` HTML/doc extraction scraper).

## 2. Theory: Structural Authority & Transformation Mechanics

Frontier Developments generates the primary specification from internal technical documentation. `Lombra/elite-api-docs` transforms this documentation via an automated pipeline:

1. **Extraction Source (`docA.json` / `parse-html.html`):** Extracts headings, tables, code fences, and paragraphs from FDev source exports.
2. **Markdown Generator (`build.js`):** Emits structured Markdown files with normalized table headers for rank ladders, suit loadouts, and state enumerations.
3. **Static Site Delivery (`.vitepress/config.mjs`):** Compiles documentation into static HTML with search and navigation hierarchies.

### Authority Boundaries

* **Canonical Game Behavior vs. Documentation Lag:** While `elite-api-docs` provides the definitive descriptive taxonomy for Frontier's intended journal schema, discrepancies frequently occur between documented schemas and live game emission (e.g., missing optional fields, undocumented enum values, or localized string discrepancies).
* **Role in `ed-telemetry`:** `elite-api-docs` acts as the primary reference taxonomy for event names, envelope keys, status bitmask values, and snapshot payload structures, while runtime telemetry parsers must remain defensive against undocumented extensions.

## 3. Analysis: Module Inventory

The repository partitions journal documentation into functional domain modules:

| Document File | Purpose / Domain Coverage | Line Count |
| :--- | :--- | :--- |
| `docs/File Format.md` | Core JSON Lines envelope, datestamp format, file headers, localization rules | 71 |
| `docs/Status File.md` | `Status.json` specification: bitmask definitions (`Flags`, `Flags2`), coordinate resolution | 180 |
| `docs/Startup.md` | Session initialization events (`FileHeader`, `LoadGame`, `Commander`, `Materials`, `Cargo`) | 831 |
| `docs/Travel.md` | Navigation, hyperspace jumps, supercruise transitions, docking, planetary approach | 663 |
| `docs/Combat.md` | Combat encounters, interdictions, damage, hull/shield state, bounties, PvP/PvE events | 324 |
| `docs/Exploration.md` | FSS scans, DSS mapping, bio/geo signals, organic sampling, codex discoveries | 669 |
| `docs/Trade.md` | Commodity trading, black market sales, market transactions, mining refinement | 174 |
| `docs/Station Services.md` | Outfitting, shipyard, mission boards, repairs, refuel, passenger operations | 1,680 |
| `docs/Fleet Carriers.md` | Carrier purchases, maintenance, jump scheduling, micro-resource pricing | 444 |
| `docs/Powerplay.md` | Powerplay merits, salary, system voting, fortification/undermining | 138 |
| `docs/Squadrons.md` | Squadron management, promotion, rank changes, squadron banking | 124 |
| `docs/New in Odyssey.md` | On-foot mechanics: suit loadouts, micro-resources, genetic samples, backpacks | 735 |
| `docs/Other Events.md` | Auxiliary interactions: synthesized blueprints, wing events, telemetry edge-cases | 773 |
| `docs/Appendix.md` | Canonical enumeration tables: rank indices, government IDs, economies, stars | 480 |
| `docs/index.md` | Specification overview and Version 1 through Version 37 historical changelog | 209 |

## 4. Remediation: Integration Workflow for `ed-telemetry`

1. **Schema Validation:** Use `elite-api-docs` to construct domain event models and validate mandatory vs. optional parameters.
2. **Bitmask Extraction:** Transcribe integer bit position tables from `Status File.md` directly into strongly typed Python enumerations (`IntFlag`).
3. **Companion Snapshot Grounding:** Correlate external companion JSON files documented in `Station Services.md`, `Startup.md`, `Travel.md`, and `New in Odyssey.md` with the registry formalized in ADR 0007.
