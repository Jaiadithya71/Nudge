# Template — Extending an MCP Server with New Tools

> Use this template when adding tools to an **existing** MCP server (e.g. `tasks_server`).
> For a **new domain** (calendar, goals-write, nudges), clone `MCP_TASKS_SERVER_WORKSTREAM.md` instead — that's a full workstream, not an extension.

---

## How to use this template

1. Copy this file to `Planning/MCP_<SERVER>_EXTENSION_<SHORT_NAME>.md` (e.g. `MCP_TASKS_EXTENSION_ARCHIVE.md`).
2. Fill in every `<FILL IN>` block below.
3. Hand the filled template + the original `MCP_TASKS_SERVER_WORKSTREAM.md` to the agent.
4. Agent treats the original doc as the authoritative spec and this file as a scoped delta.

---

## 0. Prerequisite Reading

Agent must read before coding:
- `Planning/MCP_TASKS_SERVER_WORKSTREAM.md` — the original workstream (invariants, layout, rules).
- `mcp_servers/<server>/server.py`, `tools.py`, `api_client.py` — the current state of the server being extended.
- `Planning/SYSTEM_STATE.md` — current API surface.

All rules from §1, §7, §9, §12 of the original workstream doc **still apply**. Do not re-litigate them.

---

## 1. Extension Goal

One sentence: why are we adding these tools? Link to the user need.

> <FILL IN — e.g. "User wants to archive old tasks without deleting them, to keep the active list lean while preserving history.">

---

## 2. New Tools to Add

For each new tool, fill in the same structure as §6 of the original workstream.

### Tool: `<tool_name>`
- **Description (LLM-facing):** `<FILL IN>`
- **Input schema:** `<FILL IN — JSON shape>`
- **Output shape:** `<FILL IN>`
- **Calls:** `<FILL IN — e.g. POST /api/tasks/{id}/archive>`
- **Failure mode:** `<FILL IN>`

(Repeat the block for each tool.)

---

## 3. Required FastAPI Changes

If these tools need new endpoints or modifications, list them here. Same discipline as §5 of the original: **extend FastAPI, never reach around it.**

> <FILL IN — or write "None, all routes already exist" if so.>

---

## 4. Required Changes to Existing Server Files

Be specific. The agent should not guess.

- `tools.py` — add `<N>` new entries to `TOOL_DEFINITIONS` and `<N>` new handlers.
- `api_client.py` — add method(s): `<FILL IN>` (or "no changes").
- `tests/test_tools.py` — add unit test per new tool.
- `README.md` — update tool list.

---

## 5. Out of Scope

List what the agent must NOT do, even if tempted:

- <FILL IN — e.g. "Do not add un-archive tool in this extension; separate workstream.">
- <FILL IN>

---

## 6. Acceptance Criteria

- [ ] All new tools unit-tested.
- [ ] Live integration test: ask Claude Desktop to use each new tool; dashboard reflects the result.
- [ ] `README.md` and `SYSTEM_STATE.md` updated with the new tools.
- [ ] Existing tools still work (no regression in §11.2 of the original).
- [ ] Tool count per server stays **≤ 15**. If this extension would push past 15, stop and split into a new domain server instead.

---

## 7. The 15-Tool Soft Cap — Why It Exists

Large tool catalogs degrade LLM tool-selection accuracy. If a single MCP server grows past ~15 tools, the LLM starts choosing poorly-named neighbors or hallucinating arguments. Before adding tool #16, ask: "Is this really the same domain, or am I turning tasks_server into a god-server?" Most of the time the answer is: spin up a new server.
