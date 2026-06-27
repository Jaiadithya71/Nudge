# Workstream — Tasks MCP Server (Phase 2.5)

> **For the implementing agent.** Read this fully before writing code. Do not deviate from the architectural decisions below without flagging them first.

---

## 0. Your Role and Scope

**Before writing any code, read these three files in full:**
1. `CLAUDE.md` (repo root) — project conventions, module layout, import patterns, how the system runs.
2. `Planning/SYSTEM_STATE.md` — authoritative inventory of what exists today (endpoints, tables, modules).
3. `Planning/MCP_SPIKE_FINDINGS.md` — validated MCP patterns and gotchas from the 2-hour proof-of-concept spike.

Then return here and proceed.

---

You are building a new top-level module: `mcp_servers/tasks_server/`. It is a Python process that speaks the **Model Context Protocol (MCP)** over stdio, exposing Nudge's task operations as LLM-callable tools.

**Primary consumer:** Anthropic's Claude Desktop app (reads `claude_desktop_config.json`, spawns your process, connects via stdio).

**Secondary consumer (later):** Nudge's own chat UI in Phase 3. Do not build for that yet, but do not architect in a way that prevents it.

**You are NOT building:**
- A new chat UI
- A goals MCP server
- A calendar MCP server
- Any changes to nudge scheduling logic
- Any changes to the Next.js dashboard

If you find yourself wanting to touch any of the above, stop and ask.

---

## 1. The One Non-Negotiable Architectural Rule

**The MCP server MUST route all reads and writes through the existing FastAPI layer. It MUST NOT import from `Memory/`, `Orchestrator/`, or `Remind/` directly. It MUST NOT open `mirror.db` directly.**

```
Claude Desktop ──stdio/JSON-RPC──► MCP server ──HTTP──► FastAPI ──► SQLite
                                   (this repo)         (existing)
```

**Why this rule exists:**
- FastAPI owns all invariants (goal linking, nudge re-scheduling after task completion, vector DB re-indexing on ingest).
- Bypassing FastAPI would create a second writer with different rules — guaranteed drift within weeks.
- If FastAPI's contract is insufficient, **extend FastAPI**, do not reach around it.

Violating this rule is the #1 way this workstream fails. Do not do it.

---

## 2. Directory Layout

Create exactly this structure. Nothing more.

```
mcp_servers/
├── __init__.py              # empty
└── tasks_server/
    ├── __init__.py          # empty
    ├── README.md            # how to run + Claude Desktop config snippet
    ├── server.py            # MCP server entrypoint (main module)
    ├── api_client.py        # async httpx wrapper around FastAPI
    ├── schema_utils.py      # Gemini-compatible schema cleaner (for future consumers)
    ├── tools.py             # tool definitions (name, description, schema, handler)
    └── tests/
        ├── __init__.py
        ├── test_api_client.py   # mocks httpx
        └── test_tools.py        # mocks api_client
```

Do not create any other files. Do not add a Dockerfile, a setup.py, or a CI config in this workstream.

---

## 3. Dependencies

Add to the repo's existing `requirements.txt` (or equivalent). Do not create a separate requirements file for the MCP server.

```
mcp>=1.27.0          # Anthropic's official MCP SDK (validated in spike)
httpx>=0.27.0        # async HTTP client (FastAPI already uses this in tests)
```

No other new dependencies. Re-use `pydantic` (already present) for tool input validation if helpful.

---

## 4. Environment Configuration

The server reads these env vars at startup. Fail fast with a clear error message if any required one is missing.

| Var | Required | Default | Purpose |
|---|---|---|---|
| `NUDGE_API_URL` | yes | — | Base URL of the running FastAPI server, e.g. `http://127.0.0.1:8000` |
| `NUDGE_JWT` | yes | — | Pre-obtained JWT for the user whose tasks this server will manage |
| `NUDGE_MCP_TIMEOUT` | no | `10.0` | HTTP request timeout in seconds |
| `NUDGE_MCP_LOG_LEVEL` | no | `INFO` | Standard Python logging level |

**Key design point:** `NUDGE_JWT` is bound once at server startup. It is **not** a tool parameter. The LLM has no ability to forge or swap the user identity. One MCP server process serves exactly one user's data.

### How the user obtains a JWT (document in README.md)

```bash
# One-time, user does this manually:
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "jai"}'
# Copy the returned token into Claude Desktop config (see §10).
```

---

## 5. Required FastAPI Changes

Before the MCP server can meet its goals, FastAPI must expose two capabilities it currently lacks. Add these in a **separate commit** before the MCP server itself.

### 5.1 `GET /api/tasks` — list endpoint

Currently tasks only come bundled in `/api/context`. Add a dedicated list endpoint:

```python
# In api/routers/tasks.py (or wherever task routes live)

@router.get("/api/tasks")
async def list_tasks(
    status: Optional[Literal["pending", "overdue", "completed", "all"]] = "pending",
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user),
) -> list[TaskDict]:
    """Return tasks filtered by status for the authenticated user."""
    # Delegate to Memory.memory.list_tasks() with the right filter
```

### 5.2 `POST /api/search/tasks` — semantic search endpoint

`Memory/memory.py` already has `semantic_search()` (per SYSTEM_STATE.md: "Built, never used"). Expose it:

```python
@router.post("/api/search/tasks")
async def search_tasks(
    body: SearchRequest,  # {"query": str, "limit": int = 10}
    user_id: str = Depends(get_current_user),
) -> list[dict]:
    """Semantic search over the user's tasks ChromaDB collection.
    Returns: [{"task_id": str, "title": str, "score": float, "snippet": str}, ...]
    """
```

**Before writing §5.2**, run a manual test of `semantic_search()` to confirm it returns sensible results. If it does not, stop and surface that — do NOT ship a semantic tool that returns garbage.

---

## 6. Tool Catalog — Build Exactly These 11 Tools

Each tool below lists: **name**, **description** (what the LLM sees), **input schema**, **output shape**, **underlying FastAPI call**, and **failure mode**. Implement in `tools.py` as a list of dicts + handler functions. Do not add tools not on this list.

### CRUD (6)

#### 6.1 `list_tasks`
- **Description:** "List the user's tasks. Filter by status (pending, overdue, completed, or all). Use this to see what the user is working on right now."
- **Input:** `{ "status": "pending|overdue|completed|all" (default "pending"), "limit": int (default 50, max 200) }`
- **Output:** JSON array of task dicts (id, title, status, due_date, priority, goal_id, nudge_enabled).
- **Calls:** `GET /api/tasks?status={status}&limit={limit}`
- **Failure:** Empty array on 404; propagate 401/500 as MCP error.

#### 6.2 `get_task`
- **Description:** "Fetch a single task with all details including nudge configuration and custom nudge message."
- **Input:** `{ "task_id": str (required) }`
- **Output:** Full task dict.
- **Calls:** `GET /api/tasks/{task_id}` — **add this endpoint too if not present.**
- **Failure:** MCP error with "task not found" on 404.

#### 6.3 `create_task`
- **Description:** "Create a new task. Provide at minimum a title. Optional: notes, due_date (YYYY-MM-DD), priority (low/medium/high), goal_id to link to a goal, and nudge configuration (nudge_enabled, nudge_times as list of HH:MM strings, nudge_days as list of weekday names, nudge_message as custom reminder text)."
- **Input:** Full task schema, only `title` required.
- **Output:** Created task dict including assigned `id`.
- **Calls:** `POST /api/tasks` with JSON body.

#### 6.4 `update_task`
- **Description:** "Update fields on an existing task. Only pass the fields you want to change."
- **Input:** `{ "task_id": str (required), ...any editable fields }`
- **Output:** Updated task dict.
- **Calls:** `PATCH /api/tasks/{task_id}`.

#### 6.5 `complete_task`
- **Description:** "Mark a task as completed. This also triggers nudge re-scheduling and action logging on the server side."
- **Input:** `{ "task_id": str (required) }`
- **Output:** `{ "task_id": str, "status": "completed", "completed_at": iso8601 }`
- **Calls:** `PATCH /api/tasks/{task_id}` with `{"status": "completed"}`.

#### 6.6 `delete_task`
- **Description:** "Permanently delete a task. This cannot be undone. Prefer complete_task unless the user explicitly wants to remove the task."
- **Input:** `{ "task_id": str (required) }`
- **Output:** `{ "deleted": true, "task_id": str }`
- **Calls:** `DELETE /api/tasks/{task_id}`.

### Context / semantic (3)

#### 6.7 `find_similar_tasks`
- **Description:** "Find tasks semantically similar to a natural-language query. Use this when the user describes something fuzzy like 'the thing about the insurance' rather than naming the exact task."
- **Input:** `{ "query": str (required), "limit": int (default 10, max 50) }`
- **Output:** `[{ "task_id": str, "title": str, "score": float, "snippet": str }, ...]`
- **Calls:** `POST /api/search/tasks`.

#### 6.8 `get_daily_context`
- **Description:** "Return the user's current-day snapshot: goals, today's tasks grouped by status, today's calendar events, and recent actions. Use this at the start of a conversation to ground yourself in the user's current state."
- **Input:** `{}` (no parameters)
- **Output:** Trimmed UserContext dict — drop fields the LLM does not need (full contact list, vector embeddings).
- **Calls:** `GET /api/context`, then filter/summarize in Python before returning.

#### 6.9 `tasks_for_goal`
- **Description:** "List all tasks linked to a specific goal."
- **Input:** `{ "goal_id": str (required) }`
- **Output:** Array of task dicts.
- **Calls:** `GET /api/tasks?goal_id={goal_id}` — **extend the list endpoint from §5.1 to accept this filter.**

### Read-only goals (1)

#### 6.10 `list_goals`
- **Description:** "List the user's goals. Read-only from this MCP server — goal editing happens in the dashboard."
- **Input:** `{}`
- **Output:** Array of goal dicts (id, title, priority, description).
- **Calls:** `GET /api/context` and extract `.goals` (or add `GET /api/goals` if you find yourself needing it elsewhere).

### Action logging (1)

#### 6.11 `log_action`
- **Description:** "Record that the user acknowledged, snoozed, or ignored something. Call this when the user confirms they took action on a nudge or task via the conversation."
- **Input:** `{ "action_type": "acknowledged|snoozed|ignored|completed", "task_id": str (optional), "notes": str (optional) }`
- **Output:** `{ "logged": true, "action_id": str }`
- **Calls:** `POST /api/log-action`.

---

## 7. Schema Utilities (`schema_utils.py`)

Copy the schema cleaner from the MCP spike findings (Planning/MCP_SPIKE_FINDINGS.md §"What needed workarounds"). This is for **future** consumers (Gemini, OpenAI) — Claude itself accepts standard JSON Schema. Include it now so Phase 3's adapter can reuse it without a second copy springing up.

```python
UNSUPPORTED_SCHEMA_KEYS = {"additionalProperties", "$schema", "$id", "definitions", "default"}

def clean_schema_for_gemini(schema: dict) -> dict:
    """Recursively strip JSON Schema keys Gemini rejects. Safe no-op for Claude."""
    # Implement as per spike; cover nested properties, items, oneOf/anyOf.
```

Unit-test it with a schema that has all 5 offending keys plus nested examples.

---

## 8. The MCP Server Entrypoint (`server.py`)

Use the MCP SDK's high-level `Server` class. Shape:

```python
import asyncio
import logging
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .api_client import NudgeAPIClient
from .tools import TOOL_DEFINITIONS, dispatch_tool

def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Required env var {name} is not set")
    return v

async def main():
    logging.basicConfig(level=os.environ.get("NUDGE_MCP_LOG_LEVEL", "INFO"))
    api_url = _require_env("NUDGE_API_URL")
    jwt = _require_env("NUDGE_JWT")
    timeout = float(os.environ.get("NUDGE_MCP_TIMEOUT", "10.0"))

    client = NudgeAPIClient(base_url=api_url, jwt=jwt, timeout=timeout)
    server = Server("nudge-tasks")

    @server.list_tools()
    async def list_tools():
        return [types.Tool(**t.mcp_definition()) for t in TOOL_DEFINITIONS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = await dispatch_tool(name, arguments, client)
        return [types.TextContent(type="text", text=result)]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

`dispatch_tool` returns a JSON-serialized string. Keep it boring and predictable — the LLM sees this text.

---

## 9. The API Client (`api_client.py`)

A thin async wrapper. One shared `httpx.AsyncClient` for the process lifetime.

Required behavior:
- Adds `Authorization: Bearer {jwt}` to every request.
- Raises a typed exception on non-2xx with: status code, endpoint, response body snippet.
- Logs every request at DEBUG, every error at WARNING.
- **Does not retry.** If the user's JWT is expired, the user needs to know — not silently hang.

```python
class NudgeAPIError(Exception):
    def __init__(self, status: int, endpoint: str, body: str):
        self.status = status
        self.endpoint = endpoint
        self.body = body
        super().__init__(f"{endpoint} -> {status}: {body[:200]}")

class NudgeAPIClient:
    def __init__(self, base_url: str, jwt: str, timeout: float = 10.0): ...
    async def get(self, path: str, params: dict | None = None) -> Any: ...
    async def post(self, path: str, json: dict) -> Any: ...
    async def patch(self, path: str, json: dict) -> Any: ...
    async def delete(self, path: str) -> Any: ...
    async def aclose(self) -> None: ...
```

---

## 10. Claude Desktop Configuration

Document this exact block in `mcp_servers/tasks_server/README.md`. The user pastes it into `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS).

```json
{
  "mcpServers": {
    "nudge-tasks": {
      "command": "python",
      "args": ["-m", "mcp_servers.tasks_server.server"],
      "cwd": "C:\\Users\\Jaiadithya\\Personal_Work_Related\\Nudge",
      "env": {
        "NUDGE_API_URL": "http://127.0.0.1:8000",
        "NUDGE_JWT": "<paste JWT here>",
        "NUDGE_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Startup order the user must follow (document in README):
1. Start FastAPI: `uvicorn api.main:app --reload`
2. Obtain JWT via `/api/auth/login`
3. Paste JWT into Claude Desktop config, restart Claude Desktop
4. The `nudge-tasks` tools appear in Claude Desktop's tool picker.

---

## 11. Testing Protocol

### 11.1 Unit tests (must pass in CI)
- `test_api_client.py` — mock `httpx.AsyncClient`, verify JWT header injection, verify error typing.
- `test_tools.py` — mock `NudgeAPIClient`, call each of the 11 tools once, assert the expected FastAPI path is hit with correct method/body.
- `test_schema_utils.py` — feed a schema with all 5 offending keys at root and nested, verify cleaner strips them without breaking valid keys.

### 11.2 Live integration test (manual, documented in README)
1. Run FastAPI locally with a test user.
2. Seed 3 tasks via the dashboard.
3. Start Claude Desktop with the MCP config.
4. In a Claude conversation, ask: "What are my pending tasks?" → expect `list_tasks` to fire.
5. Ask: "Mark the first one done." → expect `complete_task` to fire.
6. Ask: "Find anything related to insurance." → expect `find_similar_tasks` to fire.
7. Open the dashboard in a browser — confirm the state matches.

If any of those 6 steps fails, the workstream is not done.

### 11.3 What NOT to test
- Do not write tests that spawn actual stdio subprocesses. The MCP SDK's own test suite covers the protocol layer.
- Do not write tests that require a running FastAPI server for unit-level validation. Mock at the `api_client` boundary.

---

## 12. Guardrails — Things Not To Do

- ❌ Do not add `user_id` as a parameter to any tool. It is bound at startup via JWT only.
- ❌ Do not open `mirror.db` with sqlite3.
- ❌ Do not import from `Memory/`, `Orchestrator/`, `Remind/`, or `llm_module/`.
- ❌ Do not add retries to the API client.
- ❌ Do not cache FastAPI responses inside the MCP server (FastAPI already caches where needed).
- ❌ Do not add tools outside the 11 listed in §6.
- ❌ Do not change the nudge engine, scheduler, or any existing FastAPI endpoint's behavior. Only add new endpoints as specified in §5.
- ❌ Do not write tests that rely on the `.env` file or real API keys.

---

## 13. Acceptance Criteria

This workstream is complete when **all** of the following are true:

1. ✅ Two new FastAPI endpoints exist (§5.1, §5.2) with matching tests.
2. ✅ `mcp_servers/tasks_server/` contains exactly the files listed in §2.
3. ✅ All 11 tools from §6 are implemented and unit-tested.
4. ✅ `python -m mcp_servers.tasks_server.server` starts without error when env vars are set.
5. ✅ `python -m mcp_servers.tasks_server.server` exits with a clear error message when any required env var is missing.
6. ✅ Claude Desktop successfully loads the server (no red error indicator in the MCP panel).
7. ✅ All 6 steps of the live integration test in §11.2 pass.
8. ✅ `README.md` in the server folder documents: prerequisites, JWT acquisition, Claude Desktop config, troubleshooting.
9. ✅ `Planning/SYSTEM_STATE.md` is updated with a new section documenting the MCP server's existence. (Short — one paragraph plus a tool list.)
10. ✅ No new top-level dependencies beyond `mcp` and `httpx`.

---

## 14. Questions You Should Ask Before Coding

If the answer to any of these is unclear from the above, ask before writing code:

1. Is `semantic_search()` in `Memory/memory.py` actually returning sensible results today, or does it need debugging first? (Verify manually before §5.2.)
2. Does a `GET /api/tasks/{task_id}` endpoint exist? If not, does §6.2 require adding it?
3. Does `/api/log-action` accept the action_type values listed in §6.11?
4. Is there an existing `get_current_user` dependency in the FastAPI codebase, or do you need to trace the auth flow first?

Do not guess on any of these. Read the existing code, or ask.

---

## 15. Out of Scope (For Future Workstreams, Not Now)

- Goals CRUD via MCP (read-only for now per §6.10).
- Calendar tools (future Google Calendar MCP workstream).
- Multi-user session handling (current design is one-process-per-user).
- Paid-tier LLM wiring (deferred until Phase 3).
- Nudge scheduling tools (deferred — too much invariant surface).
- Chat UI (deferred to Phase 3).

If the user asks for any of these during this workstream, politely decline and note it belongs in a later phase.
