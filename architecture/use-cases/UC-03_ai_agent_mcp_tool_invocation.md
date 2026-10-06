---
title: "Use-Case Specification: UC-03 AI Agent MCP Tool Invocation"
use_case_id: "UC-03"
status: "draft"
version: "1.0.0"
level: "sea_level"
primary_actor: "AI Co-Pilot / Coding Assistant"
created_at: "2026-10-06"
last_updated_at: "2026-10-06"
---

# Use-Case Specification: UC-03 AI Agent MCP Tool Invocation

## 1. Description
An AI Assistant or Co-Pilot (e.g. Antigravity, Claude Desktop) connects to `ed-telemetry` via the Model Context Protocol (MCP) to discover and execute live game telemetry tools, answering natural language questions about current commander status, ship loadouts, and galaxy navigation.

---

## 2. Actors
* **Primary Actor:** AI Assistant / Co-Pilot Client (MCP Host)
* **Secondary Actors:** Human Player (querying the AI), `ed-telemetry` MCP Server.

---

## 3. Pre-Conditions
1. Package installed with server extra: `pip install ed-telemetry[server]`.
2. MCP host configured to launch `ed-telemetry serve --mcp` via stdio or SSE.

---

## 4. Basic Flow (Main Success Scenario)
1. AI Host launches `ed-telemetry serve --mcp`.
2. System initializes `ed_app.bootstrap.build_engine()` and starts the MCP server on stdio.
3. AI Host sends standard MCP `initialize` request.
4. System returns server capabilities, declaring available tool schemas:
   - `get_cmdr_status()`: Returns commander rank, credits, and current system.
   - `get_current_ship()`: Returns ship type, hull integrity, and equipped modules.
   - `get_market_prices(commodity)`: Returns station market listings.
5. Human Player asks AI: *"Where am I docked right now, and what ship am I flying?"*
6. AI Host invokes tool: `call_tool("get_cmdr_status", {})`.
7. `ed_app.mcp.server` queries the Core Telemetry Engine and formats response.
8. System returns tool result containing current system and station name.
9. AI synthesizes natural language answer for the player.
10. Connection persists until AI host closes the stdio transport.

---

## 5. Alternative Flows
* **6a. Core Telemetry Not Yet Populated (Game Not Started):**
  1. Tool call is invoked before player launches game.
  2. System returns status: `{"status": "offline", "message": "No active Elite Dangerous journal log detected."}`.
  3. AI informs player that the game client is not currently running.

---

## 6. Post-Conditions
* Real-time game telemetry is safely accessible by LLM agents via standard MCP schemas.
