---
title: "Master Risk Register"
tags: ["architecture", "risk", "register"]
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Master Risk Register

Barry Boehm Risk Exposure ($RE = P \times I$) log for the `ed-telemetry` project lifecycle.

---

## Active Risk Log

| Risk ID | Title / Risk Description | Probability ($P$) | Impact ($I$) | Exposure ($RE$) | Status | Mitigation Strategy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **RISK-01** | **Journal Event Schema Drift:** Undocumented game updates introduce unexpected fields into Journal logs. | 4 | 3 | **12** | active | Use resilient Pydantic parsing with `extra="allow"` to capture unmapped properties without throwing validation exceptions. |
| **RISK-02** | **Frontier CAPI OAuth Dependency:** Frontier API access policy changes or restricts third-party client registration. | 3 | 4 | **12** | active | Treat CAPI as an optional secondary adapter; guarantee 100% telemetry operations function solely via local Journal files. |
| **RISK-03** | **EDDN Schema Rejection:** Outbound telemetry payloads fail EDDN gateway validation. | 3 | 4 | **12** | active | Embed official EDDN JSON schemas in `ed_egress` test harness and validate all payloads prior to transmission. |
