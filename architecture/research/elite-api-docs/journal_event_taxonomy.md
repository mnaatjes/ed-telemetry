---
title: "Repository Research: elite-api-docs Journal Event Taxonomy"
tags: ["research", "reference", "journal-events", "elite-api-docs"]
created_at: "2026-10-08"
last_updated_at: "2026-10-08"
---

# Repository Research: elite-api-docs Journal Event Taxonomy

## 1. Diagnostic: Event Envelope & Serialization Mechanics

All Player Journal files (`Journal.<timestamp>.<part>.log`) conform strictly to line-delimited JSON (JSON Lines / NDJSON). Each line represents an independent JSON object terminated by a newline.

### Universal Event Envelope

Every journal event envelope adheres to the base schema:

```json
{
  "timestamp": "2023-05-14T08:12:30Z",
  "event": "EventName",
  "...": "domain_payload"
}
```

* **`timestamp`:** UTC timestamp formatted in ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`). Milliseconds are typically omitted by the game engine, though high-frequency combat entries may serialize identical timestamp strings across sequential lines.
* **`event`:** Case-sensitive string matching the PascalCase event name (e.g., `FileHeader`, `LoadGame`, `FSDJump`, `ScanOrganic`).

### The Heading Entry (`FileHeader`)

The first line of every journal part file is guaranteed to be a `FileHeader` event:

```json
{
  "timestamp": "2023-05-14T08:12:00Z",
  "event": "fileheader",
  "part": 1,
  "language": "English/UK",
  "Odyssey": true,
  "gameversion": "4.0.0.100",
  "build": "r291245 "
}
```

* Note: In some legacy or Horizon versions, `"event"` was lowercased (`"fileheader"`), whereas other events use PascalCase (`"FileHeader"`). The parser must handle case-insensitivity on this initial event identifier.
* When a journal exceeds size limits or a game session continues across parts, the active log file is closed and a new part file is opened, starting with an incremented `part` value and emitting a subsequent `"event": "Continued"` indicator.

## 2. Theory: Localization Architecture

Frontier utilizes internal game database string tokens prefixed with `$` and suffixed with `;` for symbolic identifiers:

```text
$symbolname;
```

When localized text is available, the journal serializes both the internal token and the translated human-readable text under a key appended with `_Localised`:

```json
{
  "timestamp": "2023-05-14T08:14:10Z",
  "event": "Government",
  "Government": "$government_PrisonColony;",
  "Government_Localised": "Colonie pénitentiaire"
}
```

### Omission Invariant

If the human-readable string is identical to the raw symbol name (common in English or standard nomenclature like materials/commodities), the `_Localised` field is omitted:

```json
{
  "Name": "iron",
  "Count": 2
}
```

Parser engines in `ed-telemetry` must never assume `_Localised` is unconditionally present; fallback to stripping `$` and `;` from the raw token is mandatory.

## 3. Analysis: Functional Event Domains

The 13 functional modules document over 250 individual journal event types:

### 1. Session Lifecycle & State Initialization (`Startup.md`)
* **Events:** `FileHeader`, `ClearSavedGame`, `NewCommander`, `Commander`, `LoadGame`, `Materials`, `Cargo`, `Loadout`, `Powerplay`, `Progress`, `Rank`, `Reputation`, `Statistics`, `Missions`, `Music`, `Resurrect`.
* **Characteristics:** Emitted in an immediate burst during game startup. Establishes commander identity, current credits, loan debt, ship loadout, and inventory tallies.

### 2. Space Travel & Navigation (`Travel.md`)
* **Events:** `ApproachBody`, `ApproachSettlement`, `Docked`, `DockingCancelled`, `DockingDenied`, `DockingGranted`, `DockingRequested`, `DockingTimeout`, `FSDJump`, `FSDTarget`, `LeaveBody`, `Liftoff`, `Location`, `NavRoute`, `NavRouteClear`, `StartJump`, `SupercruiseEntry`, `SupercruiseExit`, `SupercruiseDestinationDrop`, `Touchdown`, `Undocked`.
* **Characteristics:** High spatial relevance. Contains star system coordinates (`StarPos`: `[x, y, z]`), body names, planetary landing positions (`Latitude`, `Longitude`), and jump metrics (`JumpDist`, `FuelUsed`).

### 3. Planetary Exploration & Biology (`Exploration.md`)
* **Events:** `BuyExplorationData`, `CodexEntry`, `DiscoveryScan`, `FSSAllBodiesFound`, `FSSBodySignals`, `FSSDiscoveryScan`, `FSSSignalDiscovered`, `MaterialCollected`, `MaterialDiscarded`, `MaterialDiscovered`, `MultiSellExplorationData`, `NavBeaconScan`, `SAAScanComplete`, `SAASignalsFound`, `Scan`, `ScanBaryCentre`, `ScanOrganic`, `SellExplorationData`, `SellOrganicData`.
* **Characteristics:** Extensive nested structures for celestial body composition (atmospheres, volcanism, rings, materials) and Odyssey exobiology sampling (`Genus`, `Species`, `Variant`).

### 4. Space & Ground Combat (`Combat.md`)
* **Events:** `Bounty`, `CapShipBond`, `Died`, `EscapeInterdiction`, `FactionKillBond`, `FighterDestroyed`, `HeatDamage`, `HeatWarning`, `HullDamage`, `Interdicted`, `Interdiction`, `PVPKill`, `ShieldOff`, `ShipTargeted`, `SRVDestroyed`, `UnderAttack`.
* **Characteristics:** Rapid event bursts during engagements. `ShipTargeted` provides progressive detail stages (Stage 0 to Stage 3) as ship scans resolve.

### 5. Economy & Station Services (`Station Services.md`, `Trade.md`)
* **Events:** `BuyAmmo`, `BuyDrones`, `CargoDepot`, `CommunityGoal`, `CommunityGoalDiscard`, `CommunityGoalJoin`, `CommunityGoalReward`, `CrewAssign`, `CrewFire`, `CrewHire`, `EngineerContribution`, `EngineerCraft`, `EngineerProgress`, `FetchRemoteModule`, `Market`, `MarketBuy`, `MarketSell`, `MiningRefined`, `ModuleBuy`, `ModuleRetrieve`, `ModuleSell`, `ModuleStore`, `ModuleSwap`, `Outfitting`, `PayBounties`, `PayFines`, `RedeemVoucher`, `RefuelAll`, `RefuelPartial`, `Repair`, `RepairAll`, `RestockVehicle`, `ScientificResearch`, `SetUserShipName`, `Shipyard`, `ShipyardBuy`, `ShipyardNew`, `ShipyardSell`, `ShipyardTransfer`, `ShipyardSwap`.
* **Characteristics:** Tracks financial transactions, inventory mutations, and triggers external companion snapshots (`Market.json`, `Outfitting.json`, `Shipyard.json`).

### 6. Odyssey On-Foot Gameplay (`New in Odyssey.md`)
* **Events:** `Backpack`, `BackpackChange`, `BookDropship`, `BookTaxi`, `BuyMicroResources`, `BuySuit`, `BuyWeapon`, `CancelDropship`, `CancelTaxi`, `CollectItems`, `CreateSuitLoadout`, `DeleteSuitLoadout`, `Disembark`, `DropItems`, `DropShipDeploy`, `Embark`, `FCMaterials`, `LoadoutEquipModule`, `LoadoutRemoveModule`, `RenameSuitLoadout`, `SellMicroResources`, `SellSuit`, `SellWeapon`, `ShipLocker`, `SwitchSuitLoadout`, `TransferMicroResources`, `TradeMicroResources`, `UpgradeSuit`, `UpgradeWeapon`, `UseConsumable`.
* **Characteristics:** Manages on-foot state transitions, suit/weapon engineering components (data, assets, goods), taxi shuttles (Apex Interstellar), and triggers `Backpack.json` / `ShipLocker.json`.

### 7. Fleet Carriers (`Fleet Carriers.md`)
* **Events:** `CarrierJump`, `CarrierBuy`, `CarrierStats`, `CarrierJumpRequest`, `CarrierDecommission`, `CarrierCancelDecommission`, `CarrierBankTransfer`, `CarrierDepositFuel`, `CarrierCrewServices`, `CarrierFinance`, `CarrierShipPack`, `CarrierModulePack`, `CarrierTradeOrder`, `CarrierDockingPermission`, `CarrierNameChanged`, `CarrierJumpCancelled`.
* **Characteristics:** Large-scale asset tracking, jumping mechanics, financial reserves, and market management.

### 8. Auxiliary Disciplines (`Powerplay.md`, `Squadrons.md`, `Other Events.md`)
* **Events:** `PowerplayJoin`, `PowerplayDefect`, `PowerplayLeave`, `PowerplayVote`, `PowerplayVoucher`, `SquadronCreated`, `SquadronStartup`, `AppliedToSquadron`, `DisbandedSquadron`, `AfmuRepairs`, `CockpitBreached`, `CommitCrime`, `Continued`, `CrimeVictim`, `DatalinkScan`, `DatalinkVoucher`, `DataScanned`, `DockFighter`, `DockSRV`, `FuelScoop`, `LaunchFighter`, `LaunchSRV`, `RebootRepair`, `Resupply`, `SelfDestruct`, `SendText`, `Shutdown`, `Synthesis`, `SystemsShutdown`, `USSDetection`, `VehicleSwitch`, `WingAdd`, `WingInvite`, `WingJoin`, `WingLeave`.

## 4. Remediation: Architectural Guidance for Event Ingestion

* **Strict Stream Ingestion:** Ingestion engines must treat the journal as an append-only byte stream. Lines must be split cleanly on `\n` or `\r\n` without assuming JSON multi-line formatting.
* **Schema Evolution:** Frontier frequently adds fields to events without incrementing major journal versions. Event models must accept arbitrary extra keys (`model_config = ConfigDict(extra="allow")` in Pydantic V2).
* **Timestamp Normalization:** Timestamps must be normalized to standard UTC `datetime` objects.
