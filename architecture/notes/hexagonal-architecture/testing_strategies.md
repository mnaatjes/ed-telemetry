---
title: "Hexagonal Architecture Testing Strategies & Test Catalog"
tags: ["hexagonal-architecture", "testing", "acceptance-tests", "test-doubles", "reference"]
created_at: "2026-10-12"
last_updated_at: "2026-10-12"
---

# Hexagonal Architecture Testing Strategies & Test Catalog

Tactical guide to test classifications, test doubles, and acceptance test cases synthesized from Garrido de Paz's implementation guides.

---

## Testing Boundary Philosophy

* **The Primary Test Driver:** In Hexagonal Architecture, an automated test case is the **first and most critical driver actor** of the system.
* **Hexagon in Isolation:** Acceptance tests run directly against Driver Ports using In-Memory Test Doubles for Driven Ports.
* **No Network / No DB:** Pure hexagon acceptance tests execute 100% in memory with microsecond latency.

---

## Test Double Taxonomy (Driven Side)

| Double Type | Role in Hexagonal Architecture | Practical Example |
| :--- | :--- | :--- |
| **Stub** | Provides canned, hardcoded answers to calls from the Hexagon. | `HabitacionStubRepositorio` returning fixed room lists and daily rates. |
| **Fake** | Working implementation with an in-memory shortcut (not production ready). | `ReservaFakeRepositorio` using an in-memory `HashMap` or `List`. |
| **Mock** | Verifies specific method interactions, call counts, or signatures. | Payment gateway mock verifying `.charge(amount)` was called once. |

---

## Catalog of Real-World Tests (Author's Implementations)

### 1. HexaHotel Acceptance Test (Isolated In-Memory)
From `es.uhu.etsi.tallerhexagonal.hexahotel`:

* **Driver Port Tested:** `RealizarReservasPort`
* **Driven Ports Doubled:** `ConsultarHabitacionesPort` (Stub), `PersistirReservasPort` (Fake)
* **Test Case:** `deberia_reservar_la_unica_libre`
  * **Given:**
    * Room repository stub has rooms `101` and `102` at €50.00/day.
    * Reservation repository has existing bookings for room `101` (Dec 1–4) and `102` (Dec 10–12).
  * **When:**
    * User requests a booking from Dec 3 to Dec 7 for `prueba3@gmail.com`.
  * **Then:**
    * System selects room `102` (only vacant room during requested period).
    * Calculates total price: 4 nights $\times$ €50 = €200.00.
    * Persists new reservation with code `"3"` in the fake repository.

### 2. BlueZone BDD Acceptance Scenarios (Cucumber)
From `bluezone.adapter.forparkingcars.test`:

* **Driver Port Tested:** `ForParkingCars`
* **Scenario A: Rate Inquiry**
  * **When:** Driver requests all parking rates.
  * **Then:** System returns map of active rate plans (Hourly cost, min/max minutes, active schedule intervals).
* **Scenario B: Issue Valid Parking Permit**
  * **Given:** Rate "Zone A" active, permit rate is €1.50/hour, no existing active permit for plate `1234-XYZ`.
  * **When:** Driver requests permit for 60 minutes with valid payment card.
  * **Then:** Permit is issued with unique ticket code, valid expiration datetime, and card is billed €1.50.
* **Scenario C: Reject Duplicate Active Permit**
  * **Given:** Active permit already exists for plate `1234-XYZ` under "Zone A".
  * **When:** Driver requests another permit for same plate and rate.
  * **Then:** Hexagon rejects request until current permit expires.

### 3. BlueZone Inspection Tests (TestNG)
From `bluezone.adapter.forcheckingcars.test`:

* **Driver Port Tested:** `ForCheckingCars`
* **Test Case A: Legally Parked Car**
  * **Given:** Car plate `1234-XYZ` has active permit in "Zone A" expiring at 15:00. Current clock is 14:30.
  * **When:** Inspector checks `illegallyParkedCar(clock, "1234-XYZ", "Zone A")`.
  * **Then:** Returns `false`.
* **Test Case B: Illegally Parked Car (Expired Permit)**
  * **Given:** Car plate `1234-XYZ` permit expired at 14:00. Current clock is 14:30.
  * **When:** Inspector checks `illegallyParkedCar(clock, "1234-XYZ", "Zone A")`.
  * **Then:** Returns `true`.

---

## Testing Progression Across Delivery Stages

1. **Stage S1:** Tests run against hardcoded returns from Hexagon classes (`HardCodedCarParker`, `HardCodedCarChecker`) to prove the driver port contract works.
2. **Stage S2:** Tests run against real domain logic wired to stubs/fakes. All business use-case edge cases are verified here.
3. **Stage S3–S4:** Contract/integration tests verify individual real adapters (e.g. MariaDB adapter against testcontainers) independent of business logic.
