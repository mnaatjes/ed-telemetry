---
title: "Third-Party Telemetry Schemas, Payload Envelopes, and Integration Contracts"
tags: ["third-party-api", "eddn", "inara", "edsm", "edastro", "schemas", "payloads", "json", "research"]
created_at: "2026-10-26"
last_updated_at: "2026-10-26"
---

# Third-Party Telemetry Schemas, Payload Envelopes, and Integration Contracts

## 1. Executive Summary

This research specification establishes the authoritative integration catalog for third-party *Elite Dangerous* telemetry consumers:
1. **EDDN (Elite Dangerous Data Network):** Community crowd-sourced public relay.
2. **Inara API:** Commander profile, fleet, engineering, and flight log ledger.
3. **EDSM (Elite Dangerous Star Map) API:** Astrometrics, flight paths, and celestial discovery catalog.
4. **EDAstro (Elite Dangerous Astronomy) API:** Galactic fleet carrier logistics and traffic mapping.

It catalogs where schemas are defined (public Git repositories, OpenAPI/JSON schemas, or client reference implementations), contrasts their JSON wire payload structures, and demonstrates how raw Frontier journal events are scrubbed and transformed for each destination.

---

## 2. Schema Availability & Source Locations

| Ecosystem | Schema Availability | Authoritative Canonical Source | Schema Format |
| :--- | :--- | :--- | :--- |
| **EDDN** | **Fully Public & Versioned** | GitHub: `EDCD/EDDN` (`https://github.com/EDCD/EDDN/tree/master/schemas`) | Draft-07 JSON Schema (`$schemaRef`) |
| **Inara** | **Public Web Documentation** | Inara API v1 Doc: `https://inara.cz/inara-api/` | Custom JSON RPC / Event Batch specification |
| **EDSM** | **Public Web Documentation** | EDSM API v1 Doc: `https://www.edsm.net/en/api-v1` | Form-encoded POST + Embedded JSON String |
| **EDAstro** | **Client Whitelist & Endpoint** | EDMC Core: `plugins/edastro_core.py` & `https://edastro.com/api/journal` | Whitelisted JSON event payload |

---

## 3. Categorized Payload Envelopes

### 3.1 EDDN (Elite Dangerous Data Network)
* **Transport:** ZeroMQ Relay (`tcp://eddn.edcd.io:9500`) or HTTP Gateway (`https://eddn.edcd.io/upload/`).
* **Header Structure:** Explicit software identification, game build, and `uploaderID`.
* **Payload Structure:**
```json
{
  "$schemaRef": "https://eddn.edcd.io/schemas/journal/1",
  "header": {
    "softwareName": "ed-telemetry [Linux]",
    "softwareVersion": "0.6.0",
    "uploaderID": "adulantis",
    "gameversion": "4.4.2.1",
    "gamebuild": "r314159"
  },
  "message": {
    "timestamp": "2026-10-26T01:00:00Z",
    "event": "FSDJump",
    "StarSystem": "Sol",
    "SystemAddress": 10477373803,
    "StarPos": [0.0, 0.0, 0.0],
    "SystemAllegiance": "Federation",
    "SystemEconomy": "$economy_Refinery;",
    "SystemSecondEconomy": "$economy_Industrial;",
    "SystemGovernment": "$government_Democracy;",
    "SystemSecurity": "$SYSTEM_SECURITY_high;",
    "Population": 11000000000,
    "Body": "Sol",
    "BodyID": 0,
    "BodyType": "Star"
  }
}
```
* **Enforced Scrubbing:** EDDN servers validate incoming messages against strict JSON Schemas. `FID`, `FuelLevel`, `Wanted`, `CockpitBreach`, and `ActiveFine` are **strictly prohibited** and will cause HTTP 400 rejection.

---

### 3.2 Inara API v1
* **Transport:** HTTPS POST to `https://inara.cz/inapi/v1/`.
* **Envelope Structure:** A single top-level `header` containing Commander credentials and client metadata, followed by an ordered array of `events`.
* **Payload Structure:**
```json
{
  "header": {
    "appName": "ed-telemetry",
    "appVersion": "0.6.0",
    "isDeveloped": false,
    "APIkey": "9a8b7c6d5e4f3a2b1c0d",
    "commanderName": "adulantis",
    "commanderFrontierID": "F5611068"
  },
  "events": [
    {
      "eventName": "addCommanderTravelFSDJump",
      "eventTimestamp": "2026-10-26T01:00:00Z",
      "eventData": {
        "starsystemName": "Sol",
        "starsystemCoordinates": [0.0, 0.0, 0.0],
        "jumpDistance": 34.2
      }
    },
    {
      "eventName": "setCommanderCredits",
      "eventTimestamp": "2026-10-26T01:00:01Z",
      "eventData": {
        "commanderCredits": 5235083083,
        "commanderLoan": 0
      }
    }
  ]
}
```
* **Specific Inara Invariant:** Inara maps raw journal events to namespaced RPC verbs (e.g. `FSDJump` -> `addCommanderTravelFSDJump`, `Cargo` -> `setCommanderInventoryCargo`, `Materials` -> `setCommanderInventoryMaterials`).

---

### 3.3 EDSM (Elite Dangerous Star Map) API
* **Transport:** HTTPS POST to `https://www.edsm.net/api-journal-v1/`.
* **Envelope Structure:** Sent as standard HTTP POST form data (`application/x-www-form-urlencoded`) where the `message` field contains a JSON-serialized string of events.
* **Payload Structure:**
```json
{
  "commanderName": "adulantis",
  "apiKey": "1234567890abcdef",
  "fromSoftware": "ed-telemetry",
  "fromSoftwareVersion": "0.6.0",
  "fromGameVersion": "4.4.2.1",
  "fromGameBuild": "r314159",
  "message": "[{\"timestamp\":\"2026-10-26T01:00:00Z\",\"event\":\"FSDJump\",\"StarSystem\":\"Sol\",\"StarPos\":[0.0,0.0,0.0],\"JumpDist\":34.2}]"
}
```
* **Specific EDSM Invariant:** Unlike Inara, EDSM accepts raw Frontier journal JSON syntax directly inside the `message` list. It does not require or accept `FID`.

---

### 3.4 EDAstro (Elite Dangerous Astronomy) API
* **Transport:** HTTPS POST to `https://edastro.com/api/journal`.
* **Envelope Structure:** Sent directly as a JSON object containing filtered events focused exclusively on fleet carrier movements, deep space exploration, and star system discoveries.
* **Payload Structure:**
```json
{
  "timestamp": "2026-10-26T01:00:00Z",
  "event": "CarrierJumpRequest",
  "CarrierID": 3715110400,
  "SystemName": "Wregoe YP-G d10-27",
  "Body": "Wregoe YP-G d10-27 3",
  "SystemAddress": 849204910293
}
```
* **Whitelisted Properties:** EDAstro uses strict field whitelisting (`CarrierStats`, `CarrierJumpRequest`, `FSSDiscoveryScan`, `FSSAllBodiesFound`). All player balances, outfitting, personal names, and `FID` are ignored.

---

## 4. Field Transformation & Redaction Comparison

Below is a direct comparison of how a single **`FSDJump`** journal event is transformed across destinations:

### Raw Journal Source Event
```json
{
  "timestamp": "2026-10-26T01:00:00Z",
  "event": "FSDJump",
  "StarSystem": "Sol",
  "SystemAddress": 10477373803,
  "StarPos": [0.0, 0.0, 0.0],
  "SystemAllegiance": "Federation",
  "SystemEconomy": "$economy_Refinery;",
  "SystemSecondEconomy": "$economy_Industrial;",
  "SystemGovernment": "$government_Democracy;",
  "SystemSecurity": "$SYSTEM_SECURITY_high;",
  "Population": 11000000000,
  "Body": "Sol",
  "BodyID": 0,
  "BodyType": "Star",
  "JumpDist": 34.21,
  "FuelUsed": 3.45,
  "FuelLevel": 12.55,
  "Wanted": false
}
```

### Transformation Across Targets

| Destination | Event Name / Verb | `JumpDist` | `FuelUsed` / `FuelLevel` | `Wanted` | `FID` in Envelope | `cmdr` in Envelope |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EDDN** | `FSDJump` (Generic) | **Scrubbed** | **Scrubbed** | **Scrubbed** | **Never Sent** | `uploaderID` (Header) |
| **Inara** | `addCommanderTravelFSDJump` | **Included** | **Scrubbed** | N/A | **`commanderFrontierID`** | **`commanderName`** |
| **EDSM** | `FSDJump` (Raw) | **Included** | **Included** | **Included** | **Never Sent** | **`commanderName`** |
| **EDAstro** | `FSDJump` | N/A | N/A | N/A | **Never Sent** | **Never Sent** |

---

## 5. Architectural Recommendations for `ed-telemetry`

To implement outbound egress plugins in `ed_telemetry.adapters.driven.egress`:
1. **Core Decoupling:** Keep SQLite storage (`telemetry.db`) raw and unscrubbed so that historical replays retain full fidelity for Inara/EDSM.
2. **Dedicated Egress Serializers:**
   - `InaraEgressAdapter`: Transforms domain events into Inara's custom RPC schema with `APIkey`, `commanderName`, and `commanderFrontierID`.
   - `EdsmeEgressAdapter`: Encapsulates batch arrays into form-encoded POST payloads with `apiKey` and `commanderName`.
   - `EddnEgressAdapter`: Applies JSON schema validation against `https://eddn.edcd.io/schemas/journal/1`, actively popping personal status and faction fields before publishing.
