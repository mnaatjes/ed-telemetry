---
title: "Repository Research: elite-api-docs Snapshot Files & Status.json Spec"
tags: ["research", "reference", "status-json", "snapshots", "elite-api-docs"]
created_at: "2026-10-08"
last_updated_at: "2026-10-08"
---

# Repository Research: elite-api-docs Snapshot Files & Status.json Spec

## 1. Diagnostic: The Snapshot Paradigm

Unlike the incremental, append-only journal stream, Elite Dangerous uses **snapshot files** for high-frequency or large tabular state dumps. These files reside in the identical Saved Games directory as the journal and are **completely overwritten in-place** on each update.

`elite-api-docs` documents nine primary snapshot files:
1. `Status.json` (Real-time telemetry, updated every few seconds)
2. `Market.json` (Station commodity market prices and stock)
3. `Outfitting.json` (Station module purchasing catalog)
4. `Shipyard.json` (Station shipyard catalog)
5. `NavRoute.json` (Multi-hop hyperspace plotted route)
6. `Cargo.json` (Ship cargo hold manifest)
7. `Backpack.json` (On-foot personal inventory)
8. `ShipLocker.json` (Odyssey storage locker contents)
9. `FCMaterials.json` (Fleet carrier bartender material prices)

## 2. Theory: Status.json Deep Dive

`Status.json` is the highest-frequency file emitted by Elite Dangerous. It reflects live cockpit HUD state, flight metrics, and player physical position.

### Envelope Structure

```json
{
  "timestamp": "2023-05-14T10:15:22Z",
  "event": "Status",
  "Flags": 16842765,
  "Flags2": 0,
  "Pips": [4, 8, 0],
  "FireGroup": 0,
  "GuiFocus": 0,
  "Fuel": {
    "FuelMain": 15.146626,
    "FuelReservoir": 0.382796
  },
  "Cargo": 0.0,
  "LegalState": "Clean",
  "Latitude": -28.584963,
  "Longitude": 6.826313,
  "Heading": 109,
  "Altitude": 404,
  "BodyName": "Achenar 3",
  "PlanetRadius": 6371000.0,
  "Balance": 1250000000,
  "Destination": {
    "System": 128666874400,
    "Body": 12,
    "Name": "Capitol"
  }
}
```

### Primary Flags (32-bit Integer Bitfield)

The `Flags` field is a 32-bit unsigned integer encoding fundamental vehicle and flight states:

| Bit | Hex Value | Name / State Meaning | Notes |
| :--- | :--- | :--- | :--- |
| **0** | `0x00000001` | Docked | On a landing pad (station or surface settlement) |
| **1** | `0x00000002` | Landed | On a planet surface |
| **2** | `0x00000004` | Landing Gear Down | Landing gear deployed |
| **3** | `0x00000008` | Shields Up | Ship or SRV shield active |
| **4** | `0x00000010` | Supercruise | In supercruise flight regime |
| **5** | `0x00000020` | FlightAssist Off | Flight Assist disabled |
| **6** | `0x00000040` | Hardpoints Deployed | Weapons/mining tools deployed |
| **7** | `0x00000080` | In Wing | Part of a player wing |
| **8** | `0x00000100` | Lights On | Ship/SRV exterior lights active |
| **9** | `0x00000200` | Cargo Scoop Deployed | Cargo scoop extended |
| **10** | `0x00000400` | Silent Running | Silent running heat mode engaged |
| **11** | `0x00000800` | Scooping Fuel | Fuel scoop active near star |
| **12** | `0x00001000` | SRV Handbrake | SRV handbrake active |
| **13** | `0x00002000` | SRV Turret View | Operating SRV turret |
| **14** | `0x00004000` | SRV Turret Retracted | Close to ship docking bay |
| **15** | `0x00008000` | SRV DriveAssist | Drive assist enabled |
| **16** | `0x00010000` | FSD MassLocked | In mass lock gravitational well |
| **17** | `0x00020000` | FSD Charging | FSD charging for jump or supercruise |
| **18** | `0x00040000` | FSD Cooldown | FSD cooling down after exit |
| **19** | `0x00080000` | Low Fuel | Fuel reservoir < 25% |
| **20** | `0x00100000` | Overheating | Heat level > 100% |
| **21** | `0x00200000` | Has Lat/Long | Planetary coordinates are valid |
| **22** | `0x00400000` | Is In Danger | Hostile engagement / danger state |
| **23** | `0x00800000` | Being Interdicted | Subject to FSD interdiction tether |
| **24** | `0x01000000` | In MainShip | Piloting primary commander ship |
| **25** | `0x02000000` | In Fighter | Piloting Ship-Launched Fighter (SLF) |
| **26** | `0x04000000` | In SRV | Piloting Surface Recon Vehicle |
| **27** | `0x08000000` | HUD Analysis Mode | Analysis mode active (vs Combat mode) |
| **28** | `0x10000000` | Night Vision | Night vision active |
| **29** | `0x20000000` | Altitude From Avg Radius | Altitude measured from mean sphere (orbital) |
| **30** | `0x40000000` | FSD Jump | Actively jumping hyperspace |
| **31** | `0x80000000` | SRV HighBeam | SRV high beams enabled |

### Secondary Flags2 (On-Foot & Extended States)

Introduced in Odyssey and expanded in recent updates:

| Bit | Hex Value | Name / State Meaning | Notes |
| :--- | :--- | :--- | :--- |
| **0** | `0x000001` | OnFoot | Commander is on foot |
| **1** | `0x000002` | InTaxi | Traveling in Apex shuttle or frontline dropship |
| **2** | `0x000004` | InMulticrew | Operating in another player's ship |
| **3** | `0x000008` | OnFootInStation | Inside starport concourse / interior |
| **4** | `0x000010` | OnFootOnPlanet | Exterior ground exploration |
| **5** | `0x000020` | AimDownSight | Weapon ADS engaged |
| **6** | `0x000040` | LowOxygen | Suit oxygen reserves depleted |
| **7** | `0x000080` | LowHealth | Suit health critical |
| **8** | `0x000100` | Cold | Environmental hypothermia |
| **9** | `0x000200` | Hot | Environmental hyperthermia |
| **10** | `0x000400` | VeryCold | Severe hypothermia hazard |
| **11** | `0x000800` | VeryHot | Severe hyperthermia hazard |
| **12** | `0x001000` | Glide Mode | Atmospheric entry glide mode active |
| **13** | `0x002000` | OnFootInHangar | Inside hangar bay area |
| **14** | `0x004000` | OnFootSocialSpace | Inside station bar / social area |
| **15** | `0x008000` | OnFootExterior | Outside in planetary settlement exterior |
| **16** | `0x010000` | BreathableAtmosphere | Atmosphere supports unassisted respiration |
| **17** | `0x020000` | Telepresence Multicrew | Remote holographic multicrew connection |
| **18** | `0x040000` | Physical Multicrew | Physical boarding multicrew connection |
| **19** | `0x080000` | FSD Hyperdrive Charging | Charging specifically for hyperspace system jump |
| **20** | `0x100000` | Supercruise Overdrive (SCO) | SCO boost drive active (Update 18+) |
| **21** | `0x200000` | Supercruise Assist (SCA) | SCA active, aligned, and throttled |

### GUI Focus Enumeration

`GuiFocus` denotes player UI pane engagement:
* `0`: NoFocus (default flight cockpit)
* `1`: InternalPanel (right systems panel)
* `2`: ExternalPanel (left navigation/target panel)
* `3`: CommsPanel (top communications)
* `4`: RolePanel (bottom helm/SRV/fighter panel)
* `5`: StationServices
* `6`: GalaxyMap
* `7`: SystemMap
* `8`: Orrery
* `9`: FSS mode (Full Spectrum System scanner)
* `10`: SAA mode (Detailed Surface Scanner)
* `11`: Codex

### Coordinate Emission Triggers

The documentation explicitly notes:
* Latitude / Longitude only update if position changes by **at least 0.02 degrees** when flying a ship.
* In an SRV, the position threshold drops to **0.0005 degrees**.
* When Bit 29 is unset, `Altitude` represents actual ground raycast distance in meters; when set, altitude is referenced against planetary mean radius.

## 3. Analysis: Companion Snapshot Schemas

| Snapshot File | Write Trigger | Key Schema Fields |
| :--- | :--- | :--- |
| `Market.json` | Accessing Station Commodity Market (`event: Market`) | `MarketID`, `StationName`, `StarSystem`, `Items: [{id, Name, Category, BuyPrice, SellPrice, MeanPrice, Stock, Demand, ...}]` |
| `Outfitting.json` | Accessing Station Outfitting (`event: Outfitting`) | `MarketID`, `StationName`, `StarSystem`, `Items: [{id, Name, BuyPrice}]` |
| `Shipyard.json` | Accessing Station Shipyard (`event: Shipyard`) | `MarketID`, `StationName`, `StarSystem`, `PriceList: [{id, ShipType, BaseValue}]` |
| `NavRoute.json` | Plotting or clearing route (`event: NavRoute`, `NavRouteClear`) | `Route: [{StarSystem, SystemAddress, StarPos, StarClass}]` |
| `Cargo.json` | Game startup, cargo transfers, jettison/collection (`event: Cargo`) | `Vessel`, `Count`, `Inventory: [{Name, MissionID, Count, Stolen}]` |
| `Backpack.json` | Opening or mutating on-foot suit backpack (`event: Backpack`) | `Items: [{Name, OwnerID, MissionID, Count}]`, `Components`, `Consumables`, `Data` |
| `ShipLocker.json` | Boarding ship, accessing locker terminals (`event: ShipLocker`) | Categorized inventory: `Items`, `Components`, `Consumables`, `Data` |
| `FCMaterials.json` | Interacting with Carrier Bartender (`event: FCMaterials`) | `MarketID`, `CarrierID`, `Items: [{id, Name, Price, Stock, Demand}]` |

## 4. Remediation: Ingestion Safeguards for Snapshot Files

1. **Non-Atomic File Truncation:**
   Because the game overwrites snapshot files by opening with truncate mode (`O_TRUNC` / `w`), readers will encounter empty (0-byte) or half-written JSON strings during I/O races. As established in ADR 0008, readers must debounce, retry on empty/unparseable files, and verify structural boundaries (`{...}`).
2. **Deduplication via Byte Hashing:**
   Snapshot polling (Tier 3) will frequently inspect files whose content has not changed between game frames. Fast hashing (BLAKE2b 64-bit) of raw bytes prevents unnecessary downstream deserialization.
3. **Correlation with Journal Triggers:**
   Snapshots are directly associated with journal events (e.g., `Market.json` writes immediately precede or accompany `Market` journal lines). Downstream consumers can correlate journal events with companion snapshot hashes.
