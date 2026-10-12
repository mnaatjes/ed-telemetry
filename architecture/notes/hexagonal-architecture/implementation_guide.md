---
title: "Step-by-Step Hexagonal Architecture Implementation Guide"
tags: ["hexagonal-architecture", "implementation-guide", "ports-and-adapters", "how-to"]
created_at: "2026-10-12"
last_updated_at: "2026-10-12"
---

# Step-by-Step Hexagonal Architecture Implementation Guide

Clear, modular, step-by-step roadmap for designing and implementing applications with the Ports and Adapters pattern.

---

## The 5 Implementation Stages

Follow Cockburn & Garrido de Paz's staged delivery sequence:

```
Stage S1: [ Test Suite ] ----> [ Hardcoded Hexagon ] ----> (No Driven Adapters)
Stage S2: [ Test Suite ] ----> [  Real Hexagon Logic ] ----> [ Test Doubles (Stubs/Fakes) ]
Stage S3: [ Real Driver] ----> [  Real Hexagon Logic ] ----> [ Test Doubles (Stubs/Fakes) ]
Stage S4: [ Test Suite ] ----> [  Real Hexagon Logic ] ----> [ Real Driven Adapters (DB/API)]
Stage S5: [ Real Driver] ----> [  Real Hexagon Logic ] ----> [ Real Driven Adapters (PROD)  ]
```

> [!IMPORTANT]
> **Completion Gate:** Once **Stage S2** passes, the business logic is 100% complete and verified. Adapters added in stages S3–S5 are mere plugins that must not alter business behavior.

---

## Phase 1: Application Design (The 5 Steps)

### Step 1: Identify Actors
1. **Left (Driver Actors):** Who needs the application to achieve a goal? (e.g., Web User, Parking Inspector, Test Runner).
2. **Right (Driven Actors):** Who does the application need to fulfill its tasks? (e.g., SQL Database, Rate Provider File, Payment Gateway).

### Step 2: Name the Ports
* Always use the **`forDoingSomething`** active verb naming convention:
  * **Driver Port:** What does the driver want the app for? (e.g., `ForParkingCars`).
  * **Driven Port:** What does the app want the external actor for? (e.g., `ForObtainingRates`, `ForStoringPermits`).

### Step 3: Define Driver Port APIs (Contracts)
Write the port interface and DTO contracts before any implementation:
```text
Port: ForParkingCars
Operations:
  - getAllRatesByName() -> Map<String, RateData>
  - issuePermit(clock, permitRequest) -> PermitTicket
```
* **Rule:** Never leak internal database models or HTTP request objects into port contracts. Use dedicated Port DTOs.

### Step 4: Add Default Adapters
* Pair each Driver Port with an automated test suite adapter (Cucumber, TestNG, pytest).
* Pair each Driven Port with an in-memory test double (Fake repository, Stub rate provider).

### Step 5: Diagram Boundaries
* Keep the Hexagon at the center. Ensure all dependency arrows point toward ports, never directly across the boundary.

---

## Phase 2: Project Structure & Code Layout

Organize modules/packages into isolated components:

```text
my-app/
├── myapp-hexagon/                 # ZERO external framework/DB dependencies
│   ├── driver/
│   │   └── forparkingcars/        # Public Driver Port interface + DTOs
│   │       ├── ForParkingCars.java
│   │       └── PermitRequest.java
│   ├── driven/
│   │   └── forstoringpermits/     # Public Driven Port interface + DTOs
│   │       └── ForStoringPermits.java
│   └── domain/                    # Internal business rules & services (hidden)
│
├── myapp-adapter-forparkingcars-webui/  # Driving Adapter (Web UI)
│   └── depends on: myapp-hexagon
│
├── myapp-adapter-forstoringpermits-mariadb/ # Driven Adapter (DB)
│   └── depends on: myapp-hexagon, database drivers
│
└── myapp-startup/                 # Composition Root (Bootstrap)
    └── depends on: myapp-hexagon, all adapters
```

---

## Phase 3: Bootstrap & Wiring (Startup Sequence)

The `startup` module acts as the Composition Root executing 4 precise steps:

```
[ Step 1: Instantiate Driven Adapters ]
       │  (e.g., new MariaDbPermitRepository())
       ▼
[ Step 2: Instantiate Hexagon Core ]
       │  (Inject driven adapters into Hexagon constructor)
       ▼
[ Step 3: Instantiate Driver Adapter ]
       │  (Inject Hexagon core into Driver Adapter)
       ▼
[ Step 4: Launch Driver Adapter ]
          (Execute web server, CLI entry point, or test runner)
```

### Constructor Wiring Pattern

```java
// 1. Driven side
ForStoringPermits permitRepo = new MariaDbPermitRepository(dbConfig);
ForObtainingRates rateRepo = new FileRateRepository(filePath);

// 2. Hexagon Core
ForParkingCars carParker = new ParkingService(permitRepo, rateRepo);

// 3. Driver side
DriverAdapter webAdapter = new WebUiAdapter(carParker);

// 4. Run
webAdapter.run(args);
```
