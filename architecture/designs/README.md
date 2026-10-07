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

