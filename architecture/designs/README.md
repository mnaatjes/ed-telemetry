---
title: "Software Design Documents Governance and Index"
tags: ["architecture", "designs", "sdd", "governance"]
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Software Design Documents Governance and Index

Governed by IEEE 1016-2009 (Systems Design—Software Design Descriptions) and Google Design Doc standards.

---

## 1. Quality Invariants

1. **Pre-Implementation Requirement:** An SDD must be drafted, reviewed, and approved before implementing non-trivial subsystems.
2. **The Vacation Test:** Must be sufficiently detailed for an independent engineer to build and verify the subsystem without consulting the author.
3. **The Skeptic Test:** Rigorously justify why the subsystem is required.
4. **Mandatory Visual Models:** Must include at least two Mermaid diagrams (Structural Component/Class diagram and Dynamic Sequence/Activity diagram).
5. **PR Sequencing:** Must outline phased PR milestones with verification criteria.

---

## 2. Registered Designs

| ID | Title | Status | Date | Related ADRs |
| :---: | :--- | :---: | :---: | :--- |
| **SDD-001** | [SDD-001: Modular Monorepo Baseline, Composition Root, and Automated Verification Pipeline](0001_modular_monorepo_baseline_and_verification_pipeline.md) | **draft** | 2026-10-06 | [ADR 0001](../adr/0001_architectural_vision_and_operational_concept.md), [ADR 0002](../adr/0002_verification_tooling_and_versioning_lifecycle.md) |
| **SDD-002** | [SDD-002: Operating System Path Discovery Subsystem Design](0002_os_path_discovery_component_design.md) | **draft** | 2026-10-07 | [ADR 0004](../adr/0004_os_path_discovery_and_filesystem_research_framework.md) |
| **SDD-003** | [SDD-003: Cross-Platform Testing Strategy and Simulation Matrix Design](0003_cross_platform_testing_and_simulation_matrix.md) | **draft** | 2026-10-07 | [ADR 0005](../adr/0005_cross_platform_testing_strategy_and_simulation_matrix.md) |
| **SDD-004** | [SDD-004: Active Journal Candidate Selection, Sorting, and Continuous Succession](0004_active_journal_candidate_selection_and_sorting.md) | **draft** | 2026-10-08 | [ADR 0006](../adr/0006_active_journal_candidate_selection_and_sorting.md) |
| **SDD-005** | [SDD-005: Status and Snapshot File Identification, Casing Normalization, and Trigger Architecture](0005_status_and_snapshot_file_identification.md) | **draft** | 2026-10-08 | [ADR 0007](../adr/0007_status_and_snapshot_file_identification.md) |
