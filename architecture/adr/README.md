---
title: "Architectural Decision Records Governance and Index"
tags: ["architecture", "adr", "governance", "index"]
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Architectural Decision Records Governance and Index

Governed by Markdown Architectural Decision Records (MADR 3.0).

---

## 1. Principles & Quality Invariants

1. **Immutable Historical Record:** Once committed and marked `Accepted`, an ADR is never deleted or altered to reflect new designs.
2. **Supersedence Rule:** Reversals or migrations must be recorded as a new sequential ADR explicitly citing `supersedes: ["architecture/adr/NNNN_...md"]`.
3. **Sequential Naming:** `NNNN_descriptive_slug.md` (zero-padded 4-digit index).

---

## 2. Decision Log

| Index | Title | Status | Date | Supersedes |
| :---: | :--- | :---: | :---: | :--- |
| **0001** | [ADR 0001: Architectural Vision, Operational Concept, and CI-Enforced Modular Boundaries](0001_architectural_vision_and_operational_concept.md) | **Accepted** | 2026-10-06 | — |
| **0002** | [ADR 0002: Verification Tooling, Dependency Topology, and Release Versioning Lifecycle](0002_verification_tooling_and_versioning_lifecycle.md) | **Accepted** | 2026-10-06 | — |
| **0003** | [ADR 0003: Minimal Walking Skeleton and Bootstrap Verification Contract](0003_minimal_walking_skeleton_and_bootstrap_contract.md) | **Accepted** | 2026-10-06 | — |
