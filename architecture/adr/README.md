---
title: "Architectural Decision Records Governance and Index"
tags: ["architecture", "adr", "governance", "index"]
created_at: "2026-10-06"
last_updated_at: "2026-10-09"
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
| **0004** | [ADR 0004: OS Path Discovery and Filesystem Ground-Truth Research Framework](0004_os_path_discovery_and_filesystem_research_framework.md) | **Accepted** | 2026-10-07 | — |
| **0005** | [ADR 0005: Cross-Platform Testing Strategy and Operating System Simulation Matrix](0005_cross_platform_testing_strategy_and_simulation_matrix.md) | **Accepted** | 2026-10-07 | — |
| **0006** | [ADR 0006: Active Journal Candidate Selection and Sorting Strategy](0006_active_journal_candidate_selection_and_sorting.md) | **Accepted** | 2026-10-08 | — |
| **0007** | [ADR 0007: Status and Auxiliary Snapshot File Identification and Casing Normalization](0007_status_and_snapshot_file_identification.md) | **Accepted** | 2026-10-08 | — |
| **0008** | [ADR 0008: File Ingestion Engine, Concurrency Guards, and Reactive Reactor](0008_file_ingestion_io_freshness_and_concurrency.md) | **Accepted** | 2026-10-08 | — |
| **0009** | [ADR 0009: Watcher Port Adapter and Threaded Lifecycle Management](0009_watcher_port_adapter_and_threaded_lifecycle.md) | **Accepted** | 2026-10-09 | — |
| **0010** | [ADR 0010: Application Service Layer Architecture, Boundary Contracts, and Multi-Modal Orchestration](0010_application_service_layer_and_boundary_contracts.md) | **Accepted** | 2026-10-09 | — |
| **0011** | [ADR 0011: Watcher Telemetry Application Service and Boundary Exposure](0011_watcher_telemetry_application_service.md) | **Accepted** | 2026-10-09 | — |
| **0012** | [ADR 0012: Pure Hexagonal Source Topology and Satellite SDK Segregation](0012_segregation_of_root_monorepo_topology_into_apps_and_libs.md) | **Accepted** | 2026-10-09 | ADR 0001, ADR 0002 |
| **0013** | [ADR 0013: Runtime Reflection Verification for Object-Tunneling Boundary Invariants](0013_runtime_reflection_verification_for_object_tunneling_boundaries.md) | **Accepted** | 2026-10-09 | — |
| **0014** | [ADR 0014: Driven Adapter Registry Architecture and Composition Root Integration](0014_driven_adapter_registry_architecture_and_composition_root.md) | **Accepted** | 2026-10-09 | — |
| **0015** | [ADR 0015: Daemon Application Service Orchestration and Lifecycle Supervision](0015_daemon_application_service_orchestration_and_lifecycle.md) | **Proposed** | 2026-10-10 | — |
