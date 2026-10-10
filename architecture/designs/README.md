---
title: "Software Design Documents Governance and Index"
tags: ["architecture", "designs", "sdd", "governance"]
created_at: "2026-10-06"
last_updated_at: "2026-10-09"
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
| **SDD-006** | [SDD-006: Unified File Ingestion Engine, Reactive Reactor, and Freshness Auditing](0006_file_ingestion_io_and_reactive_reactor.md) | **draft** | 2026-10-09 | [ADR 0008](../adr/0008_file_ingestion_io_freshness_and_concurrency.md) |
| **SDD-007** | [SDD-007: Watcher Port Adapter and Threaded Lifecycle Management](0007_watcher_port_adapter_and_threaded_lifecycle.md) | **approved** | 2026-10-09 | [ADR 0009](../adr/0009_watcher_port_adapter_and_threaded_lifecycle.md) |
| **0008** | [SDD-008: Application Service Layer, DTO Boundary Contracts, and Multi-Modal Orchestration](0008_application_service_layer_and_boundary_contracts.md) | **approved** | 2026-10-09 | [ADR 0010](../adr/0010_application_service_layer_and_boundary_contracts.md) |
| **0009** | [SDD-009: Watcher Telemetry Application Service and Boundary Exposure](0009_watcher_telemetry_application_service.md) | **approved** | 2026-10-09 | [ADR 0011](../adr/0011_watcher_telemetry_application_service.md) |
| **SDD-010** | [SDD-010: Pure Hexagonal Source Topology and Satellite SDK Migration](0010_pure_hexagonal_source_topology_and_satellite_sdk_migration.md) | **approved** | 2026-10-09 | [ADR 0012](../adr/0012_segregation_of_root_monorepo_topology_into_apps_and_libs.md) |
| **SDD-011** | [SDD-011: Runtime Reflection Verification for Object-Tunneling Boundary Invariants](0011_runtime_reflection_verification_for_object_tunneling_boundaries.md) | **proposed** | 2026-10-09 | [ADR 0013](../adr/0013_runtime_reflection_verification_for_object_tunneling_boundaries.md) |
| **SDD-012** | [SDD-012: Driven Adapter Registry Architecture and Composition Root Integration](0012_driven_adapter_registry_and_composition_root.md) | **proposed** | 2026-10-09 | [ADR 0014](../adr/0014_driven_adapter_registry_architecture_and_composition_root.md) |
| **SDD-013** | [SDD-013: Domain Port Protocol Genealogy, Capability Taxonomy, and Lifecycle Governance](0013_domain_port_protocol_genealogy_and_lifecycle_governance.md) | **proposed** | 2026-10-10 | [ADR 0015](../adr/0015_domain_port_protocol_genealogy_and_lifecycle_governance.md) |
