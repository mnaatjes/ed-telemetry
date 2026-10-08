---
title: "Repository Research: EDCD/EDDN Schema Governance & Validation Rules"
tags: ["research", "reference", "eddn", "json-schema", "governance"]
created_at: "2026-10-08"
last_updated_at: "2026-10-08"
---

# Repository Research: EDCD/EDDN Schema Governance & Validation Rules

## 1. Diagnostic: Schema Taxonomy

All schemas in `EDCD/EDDN` reside under `/schemas/` and conform to **JSON Schema Draft 04** (`http://json-schema.org/draft-04/schema#`).

### Canonical Schemas Inventory

| Schema File | `$id` Canonical URI | Ingestion Source | Key Purpose |
| :--- | :--- | :--- | :--- |
| `journal-v1.0.json` | `https://eddn.edcd.io/schemas/journal/1#` | Journal (`Journal.*.log`) | High-value events: `Docked`, `FSDJump`, `Scan`, `Location`, `SAASignalsFound`, `CarrierJump`, `CodexEntry` |
| `commodity-v3.0.json` | `https://eddn.edcd.io/schemas/commodity/3#` | CAPI / `Market.json` | Station commodity market pricing, supply, demand, brackets |
| `outfitting-v3.0.json` | `https://eddn.edcd.io/schemas/outfitting/3#` | CAPI / `Outfitting.json` | Available ship outfitting modules and prices |
| `shipyard-v2.0.json` | `https://eddn.edcd.io/schemas/shipyard/2#` | CAPI / `Shipyard.json` | Shipyard purchasing inventory and prices |
| `navroute-v1.0.json` | `https://eddn.edcd.io/schemas/navroute/1#` | Snapshot (`NavRoute.json`) | Multi-hop hyperspace plotted path coordinates |
| `fssbodysignals-v1.0.json`| `https://eddn.edcd.io/schemas/fssbodysignals/1#` | Journal (`FSSBodySignals`) | Biological, geological, and human signals found on bodies |
| `fssdiscoveryscan-v1.0.json`| `https://eddn.edcd.io/schemas/fssdiscoveryscan/1#` | Journal (`FSSDiscoveryScan`) | Honk results: total body count and non-body count |
| `fssallbodiesfound-v1.0.json`| `https://eddn.edcd.io/schemas/fssallbodiesfound/1#` | Journal (`FSSAllBodiesFound`) | System complete scan milestone |
| `fsssignaldiscovered-v1.0.json`| `https://eddn.edcd.io/schemas/fsssignaldiscovered/1#` | Journal (`FSSSignalDiscovered`)| Unidentified Signal Sources (USS), megaships, stations |
| `codexentry-v1.0.json` | `https://eddn.edcd.io/schemas/codexentry/1#` | Journal (`CodexEntry`) | Biological and geological regional discoveries |
| `approachsettlement-v1.0.json`| `https://eddn.edcd.io/schemas/approachsettlement/1#`| Journal (`ApproachSettlement`)| Planetary base coordinates, economy, and system address |
| `dockinggranted-v1.0.json` | `https://eddn.edcd.io/schemas/dockinggranted/1#` | Journal (`DockingGranted`) | Station landing pad allocation numbers |
| `dockingdenied-v1.0.json` | `https://eddn.edcd.io/schemas/dockingdenied/1#` | Journal (`DockingDenied`) | Denial reason (pad full, hostile, too large) |
| `fcmaterials_journal-v1.0.json`| `https://eddn.edcd.io/schemas/fcmaterials_journal/1#`| Snapshot (`FCMaterials.json`)| Carrier bartender prices uploaded via local file |
| `fcmaterials_capi-v1.0.json`| `https://eddn.edcd.io/schemas/fcmaterials_capi/1#` | CAPI endpoint | Carrier bartender prices uploaded via Frontier API |

## 2. Theory: The Three-Tier Envelope Structure

Every valid message submitted to EDDN must contain three top-level keys:

```json
{
  "$schemaRef": "https://eddn.edcd.io/schemas/journal/1",
  "header": {
    "uploaderID": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
    "softwareName": "EDMarketConnector",
    "softwareVersion": "5.10.1",
    "gameversion": "4.0.0.100",
    "gamebuild": "r291245"
  },
  "message": {
    "timestamp": "2023-05-14T08:12:30Z",
    "event": "FSDJump",
    "StarSystem": "Sol",
    "StarPos": [0.0, 0.0, 0.0],
    "SystemAddress": 10477373803
  }
}
```

1. **`$schemaRef`:** Must match an active live schema URL (or end in `/test` for development and automated tests).
2. **`header`:**
   * `uploaderID`: Client-provided persistent identifier. Salted and hashed by the gateway to preserve anonymity.
   * `softwareName` and `softwareVersion`: Required for downstream consumers to filter or quarantine data produced by buggy client releases.
   * `gameversion` and `gamebuild`: Extracted from the `FileHeader` (or `LoadGame`) journal event. Mandatory for isolating live game data from pre-release/beta mechanics.
3. **`message`:** The actual game event data, stripped of private or localized attributes.

## 3. Analysis: Privacy Scrubbing & Disallowed Properties

A foundational contribution of EDDN's schema governance is the explicit suppression of **Commander PII (Personally Identifiable Information)** and competitive tactical state.

### The `disallowed` Anti-Pattern Definition

In `schemas/journal-v1.0.json`, EDDN implements a negative JSON Schema validation construct:

```json
"definitions": {
    "disallowed": {
        "not": {
            "type": [ "array", "boolean", "integer", "number", "null", "object", "string" ]
        }
    }
}
```

Any JSON key that references `#/definitions/disallowed` **must not exist** in the payload. If present, the message is rejected with HTTP 400.

### Attributes Strictly Disallowed by EDDN

1. **Personal Financial & Legal Identity:**
   * `ActiveFine`
   * `CockpitBreach`
   * `Wanted`
   * `VoucherAmount`
   * `MyReputation`
2. **Combat & Tactical Vehicle State:**
   * `FuelLevel`
   * `FuelUsed`
   * `BoostUsed`
   * `JumpDist`
3. **Tactical Planetary Footprint:**
   * `Latitude`
   * `Longitude` (Disallowed in global journal uploads to prevent player base/fleet carrier staging tracking)
4. **Localization Strings:**
   * `patternProperties: { "_Localised$": { "$ref": "#/definitions/disallowed" } }`
   * All keys ending in `_Localised` are forbidden to save network bandwidth; downstream listeners must look up translations locally via symbol keys.

## 4. Remediation: Implications for ed-telemetry

* **Egress Scrubbing Filter:** If `ed-telemetry` supports an EDDN upload plugin, it must provide a dedicated `EDDNScrubber` transformation pipeline that purges `_Localised` attributes and all `disallowed` fields prior to transmission.
* **Schema Validation Pre-Check:** By compiling EDDN's Draft 04 JSON schemas or mirror Pydantic models, `ed-telemetry` can validate outgoing envelopes locally before transmitting network requests, reducing rejected uploads.
