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

```text
bluezone-hexagon/
├── src/main/
│   ├── driver/                      # Public Inbound Ports & DTOs
│   │   ├── forparkingcars/
│   │   └── forcheckingcars/
│   ├── driven/                      # Public Outbound Ports & Contracts
│   │   ├── forobtainingrates/
│   │   ├── forstoringpermits/
│   │   └── forpaying/
│   └── domain/                      # Internal business logic & domain entities
│       ├── model/
│       └── services/
└── pom.xml (or pyproject.toml)      # ZERO framework/database dependencies
```

---

### 2. Driver Actor (Primary Actor)
* **What it is:** The entity that triggers an interaction (e.g., Human user, CLI caller, API client, Test runner).
* **Motto:** *"Hey application, wake up and do this!"*

```text
Actors (Left Side):
├── [ Car Driver ]        --> Interacts via Web Browser / Mobile App
├── [ Parking Inspector ] --> Interacts via CLI Handheld Terminal
└── [ Automated Tests ]   --> Interacts via Cucumber BDD / Pytest Harness
```

---

### 3. Driver Port (Driving / Inbound Port)
* **What it is:** The API interface published by the hexagon for driver actors.
* **Role:** Groups use cases for a specific actor goal.
* **Implementation:** The Hexagon *implements* the Driver Port interface.
* **Naming standard:** Use the `forDoingSomething` verb pattern (e.g., `ForParkingCars`, `ForCheckingCars`).

```python
# Defined inside the Hexagon (src/core/ports/driver/for_parking_cars.py)
from abc import ABC, abstractmethod
from typing import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PermitRequest:
    car_plate: str
    rate_name: str
    duration_minutes: int


class ForParkingCars(ABC):
    """Driver Port interface grouping car parking use cases."""

    @abstractmethod
    def get_all_rates(self) -> Mapping[str, RateData]:
        """Fetch available parking rate schemes."""
        ...

    @abstractmethod
    def issue_permit(self, request: PermitRequest) -> PermitTicket:
        """Issue a verified parking permit ticket."""
        ...
```

---

### 4. Driver Adapter (Driving Adapter)
* **What it is:** Technology-specific wrapper that receives user/network input and calls the Driver Port.
* **Examples:** Web UI, REST Controller, CLI parser, Cucumber test suite.
* **Dependency:** Knows and calls the Driver Port.

```python
# Defined outside the Hexagon (src/adapters/driver/web/parking_controller.py)
from fastapi import APIRouter, Depends
from core.ports.driver.for_parking_cars import ForParkingCars, PermitRequest

router = APIRouter()


class WebParkingController:
    def __init__(self, parking_port: ForParkingCars) -> None:
        self._port = parking_port

    async def post_permit(self, body: WebPermitSchema) -> dict:
        # 1. Translate web payload into port DTO
        request = PermitRequest(car_plate=body.plate, rate_name=body.rate, duration_minutes=body.minutes)
        # 2. Invoke the Driver Port
        ticket = self._port.issue_permit(request)
        # 3. Return serialized HTTP response
        return {"ticket_id": ticket.code, "status": "ISSUED"}
```

---

### 5. Driven Actor (Secondary Actor)
* **What it is:** External system needed by the hexagon to complete a goal (e.g., DB, Payment Gateway, Mail server).
* **Two types:**
  * **Repository:** Two-way ("boomerang") data retrieval (e.g., query rates, fetch user).
  * **Recipient:** One-way ("fire and forget") notification (e.g., publish event, send email).

```text
Driven Actors (Right Side):
├── [ Relational Database ]  <-- Repository: queries/persists permit records
├── [ Rate Config File ]     <-- Repository: supplies rate timetable definitions
└── [ Payment Gateway API ]  <-- Recipient / Service: charges card synchronously
```

---

### 6. Driven Port (Outbound / SPI Port)
* **What it is:** Interface declared by the hexagon specifying what external capabilities it needs.
* **Role:** Contracts for secondary systems without leaking external technology models.
* **Implementation:** Driven Adapter *implements* the Driven Port interface.
* **Naming standard:** Use `forDoingSomething` (e.g., `ForObtainingRates`, `ForStoringPermits`, `ForPaying`).

```python
# Defined inside the Hexagon (src/core/ports/driven/for_storing_permits.py)
from abc import ABC, abstractmethod
from typing import Optional
from core.domain.permit import PermitRecord


class ForStoringPermits(ABC):
    """Driven Port contract for permit persistence."""

    @abstractmethod
    def save(self, permit: PermitRecord) -> None:
        """Persist a newly issued permit."""
        ...

    @abstractmethod
    def find_active_by_plate(self, car_plate: str) -> Optional[PermitRecord]:
        """Query active permit by plate identifier."""
        ...
```

---

### 7. Driven Adapter
* **What it is:** Concrete class implementing a Driven Port using real-world libraries or drivers.
* **Examples:** `MariadbPermitRepository`, `StripePaymentAdapter`, `FileSystemRateProvider`.

```python
# Defined outside the Hexagon (src/adapters/driven/storage/mariadb_permit_repo.py)
from core.ports.driven.for_storing_permits import ForStoringPermits
from core.domain.permit import PermitRecord
from sqlalchemy.orm import Session


class MariaDbPermitRepository(ForStoringPermits):
    """Driven Adapter fulfilling permit storage via SQLAlchemy/MariaDB."""

    def __init__(self, session_factory: Session) -> None:
        self._session_factory = session_factory

    def save(self, permit: PermitRecord) -> None:
        with self._session_factory() as session:
            db_model = DbPermitModel.from_domain(permit)
            session.add(db_model)
            session.commit()

    def find_active_by_plate(self, car_plate: str) -> Optional[PermitRecord]:
        with self._session_factory() as session:
            row = session.query(DbPermitModel).filter_by(plate=car_plate).first()
            return row.to_domain() if row else None
```

---

### 8. Default Adapter vs Real Adapter
* **Default Adapter:** Test automation tool on the driver side, or a **Test Double** (Mock, Stub, Fake) on the driven side. Used to verify the hexagon in 100% isolation.
* **Real Adapter:** Production adapter connecting to live frameworks, databases, or cloud infrastructure.

```python
# In-memory Default Adapter for unit/acceptance testing (No DB required)
class InMemoryPermitFake(ForStoringPermits):
    def __init__(self) -> None:
        self._storage: dict[str, PermitRecord] = {}

    def save(self, permit: PermitRecord) -> None:
        self._storage[permit.code] = permit

    def find_active_by_plate(self, car_plate: str) -> Optional[PermitRecord]:
        return next((p for p in self._storage.values() if p.car_plate == car_plate), None)
```

---

### 9. Configurable Dependency
* **Rule:** *"The one who triggers the interaction must know the dependency."*
* **How it works:**
  * Driver Adapter calls Driver Port $\to$ Driver Adapter knows the Hexagon.
  * Hexagon calls Driven Port $\to$ Hexagon knows the Port interface; Startup module injects the Driven Adapter.

```python
# Hexagon Core constructor injection (Driven side inversion)
class BlueZoneApplication(ForParkingCars, ForCheckingCars):
    def __init__(
        self,
        rates_port: ForObtainingRates,
        permits_port: ForStoringPermits,
        payment_port: ForPaying,
    ) -> None:
        # Core depends strictly on abstract interfaces, never concrete adapters
        self._rates = rates_port
        self._permits = permits_port
        self._payment = payment_port
```

---

### 10. Startup Module (Composition Root)
* **What it is:** The bootstrap entry point of the system.
* **The Rule:** It is the only module that knows *both* the Hexagon and all Adapters. It instantiates adapters, injects them into the hexagon, and invokes the driver adapter.

```text
bootstrap/
└── main.py (or startup module)
    ├── 1. Reads environment config & credentials
    ├── 2. Instantiates Driven Adapters (MariaDbPermitRepository, StripePaymentAdapter)
    ├── 3. Instantiates Hexagon (BlueZoneApplication) with Driven Adapters
    ├── 4. Instantiates Driving Adapters (FastAPI / CLI / Worker) with Hexagon
    └── 5. Starts runtime event loop / HTTP server
```

```python
# Example: bootstrap/main.py
def main() -> None:
    # 1. Instantiate Driven Adapters
    permit_adapter = MariaDbPermitRepository(session_pool)
    rate_adapter = FileRateProvider("/etc/bluezone/rates.json")
    payment_adapter = StripePaymentGateway(api_key=os.environ["STRIPE_KEY"])

    # 2. Wire Hexagon Core
    core_app = BlueZoneApplication(rates_port=rate_adapter, permits_port=permit_adapter, payment_port=payment_adapter)

    # 3. Wire Driving Adapter
    web_server = WebServer(port_facade=core_app)

    # 4. Run
    web_server.listen(port=8080)
```
