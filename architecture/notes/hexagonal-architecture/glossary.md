---
title: "Hexagonal Architecture Glossary"
tags: ["hexagonal-architecture", "glossary", "ports-and-adapters", "reference"]
created_at: "2026-10-12"
last_updated_at: "2026-10-12"
---

# Hexagonal Architecture Glossary

High-contrast, ADHD-friendly reference cheat sheet defining the core terms of the Ports and Adapters (Hexagonal) pattern.

---

## At a Glance: Left vs Right

| Concept | Left Side (Driver / Primary) | Center (The Hexagon) | Right Side (Driven / Secondary) |
| :--- | :--- | :--- | :--- |
| **Who initiates?** | External actor kicks the app | Processes business logic | Application kicks the external actor |
| **Who defines port?** | Hexagon defines interface | Hexagon *owns* all ports | Hexagon defines interface |
| **Who implements?** | Hexagon implements it | Business logic core | Driven Adapter implements it |
| **Dependency flow** | Driver Adapter $\to$ Hexagon | Independent of all outer tech | Hexagon $\leftarrow$ Driven Adapter (Inverted) |

---

## Core Concepts

### 1. The Hexagon (Application Core)
* **What it is:** Pure business logic and domain rules in total isolation.
* **The Rule:** Zero imports or references to databases, UI frameworks, HTTP engines, or disks.
* **Why Hexagon?** Visual metaphor representing multiple interaction ports (not limited to top-down layers).

### 2. Driver Actor (Primary Actor)
* **What it is:** The entity that triggers an interaction (e.g., Human user, CLI caller, API client, Test runner).
* **Motto:** *"Hey application, wake up and do this!"*

### 3. Driver Port (Driving / Inbound Port)
* **What it is:** The API interface published by the hexagon for driver actors.
* **Role:** Groups use cases for a specific actor goal.
* **Implementation:** The Hexagon *implements* the Driver Port interface.
* **Naming standard:** Use the `forDoingSomething` verb pattern (e.g., `ForParkingCars`, `ForCheckingCars`).

### 4. Driver Adapter (Driving Adapter)
* **What it is:** Technology-specific wrapper that receives user/network input and calls the Driver Port.
* **Examples:** Web UI, REST Controller, CLI CLI parser, Cucumber test suite.
* **Dependency:** Knows and calls the Driver Port.

### 5. Driven Actor (Secondary Actor)
* **What it is:** External system needed by the hexagon to complete a goal (e.g., DB, Payment Gateway, Mail server).
* **Two types:**
  * **Repository:** Two-way ("boomerang") data retrieval (e.g., query rates, fetch user).
  * **Recipient:** One-way ("fire and forget") notification (e.g., publish event, send email).

### 6. Driven Port (Outbound / SPI Port)
* **What it is:** Interface declared by the hexagon specifying what external capabilities it needs.
* **Role:** Contracts for secondary systems without leaking external technology models.
* **Implementation:** Driven Adapter *implements* the Driven Port interface.
* **Naming standard:** Use `forDoingSomething` (e.g., `ForObtainingRates`, `ForStoringPermits`, `ForPaying`).

### 7. Driven Adapter
* **What it is:** Concrete class implementing a Driven Port using real-world libraries or drivers.
* **Examples:** `MariadbPermitRepository`, `StripePaymentAdapter`, `FileSystemRateProvider`.

### 8. Default Adapter vs Real Adapter
* **Default Adapter:** Test automation tool on the driver side, or a **Test Double** (Mock, Stub, Fake) on the driven side. Used to verify the hexagon in 100% isolation.
* **Real Adapter:** Production adapter connecting to live frameworks, databases, or cloud infrastructure.

### 9. Configurable Dependency
* **Rule:** *"The one who triggers the interaction must know the dependency."*
* **How it works:**
  * Driver Adapter calls Driver Port $\to$ Driver Adapter knows the Hexagon.
  * Hexagon calls Driven Port $\to$ Hexagon knows the Port interface; Startup module injects the Driven Adapter.

### 10. Startup Module (Composition Root)
* **What it is:** The bootstrap entry point of the system.
* **The Rule:** It is the only module that knows *both* the Hexagon and all Adapters. It instantiates adapters, injects them into the hexagon, and invokes the driver adapter.
