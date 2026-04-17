# Nudge Tasks MCP Server

Exposes Nudge's task management as 11 LLM-callable tools via the Model Context Protocol (MCP). Claude Desktop (or any MCP-compatible client) can list, create, update, complete, delete, and semantically search your tasks — and read your goals and daily context — through natural conversation.

**All reads and writes route through the Nudge FastAPI layer. The server never touches SQLite directly.**

---

## Prerequisites

1. Python 3.11+
2. Dependencies installed: `pip install -r requirements.txt` (from the repo root)
3. The Nudge FastAPI server running: `uvicorn api.main:app --reload`
4. A valid JWT for your user (see below)

---

## Step 1 — Start FastAPI

```bash
# From the repo root
uvicorn api.main:app --reload
# Server starts at http://127.0.0.1:8000
```

---

## Step 2 — Obtain a JWT

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "jai", "password": ""}'
# Returns: {"access_token": "eyJ...", "token_type": "bearer", "user_id": "jai"}
```

Copy the `access_token` value — you'll need it in the next step.

---

## Step 3 — Configure Claude Desktop

Paste this block into your Claude Desktop config file and replace `<paste JWT here>` with the token from Step 2.

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

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

Restart Claude Desktop after saving the config.

---

## Step 4 — Verify

In a Claude Desktop conversation, ask: *"What are my pending tasks?"*
The `nudge-tasks` tools should appear in the tool picker (hammer icon), and `list_tasks` should fire automatically.

---

## Running the server manually

```bash
# From the repo root — env vars must be set in your shell or a .env file
NUDGE_API_URL=http://127.0.0.1:8000 \
NUDGE_JWT=eyJ... \
python -m mcp_servers.tasks_server.server
```

The server exits with a clear error message if `NUDGE_API_URL` or `NUDGE_JWT` is not set.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `NUDGE_API_URL` | yes | — | Base URL of the running FastAPI server |
| `NUDGE_JWT` | yes | — | Bearer JWT for the user whose tasks to manage |
| `NUDGE_MCP_TIMEOUT` | no | `10.0` | HTTP request timeout in seconds |
| `NUDGE_MCP_LOG_LEVEL` | no | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`) |

---

## Available Tools (11)

| Tool | Description |
|---|---|
| `list_tasks` | List tasks filtered by status (pending/overdue/completed/all) |
| `get_task` | Fetch a single task with full nudge config |
| `create_task` | Create a new task with optional nudge configuration |
| `update_task` | Update fields on an existing task |
| `complete_task` | Mark a task as completed |
| `delete_task` | Permanently delete a task |
| `find_similar_tasks` | Semantic search over tasks via ChromaDB |
| `get_daily_context` | Today's snapshot: tasks, goals, events, recent actions |
| `tasks_for_goal` | List all tasks linked to a specific goal |
| `list_goals` | Read-only list of user's goals |
| `log_action` | Record acknowledged/snoozed/ignored/completed actions |

---

## Troubleshooting

**Red error indicator in Claude Desktop MCP panel**
- Check that FastAPI is running and reachable at `NUDGE_API_URL`
- Check that `NUDGE_JWT` is set and not expired — re-obtain via `/api/auth/login`
- Check the Claude Desktop logs for the stderr output from this process

**`find_similar_tasks` returns empty results**
- Tasks must be ingested into ChromaDB before they appear in semantic search
- Create tasks via the dashboard first; they are embedded on creation
- Verify ChromaDB data exists at `Memory/data/{user_id}/chroma/`

**JWT expired mid-session**
- The server does not retry. Re-obtain a JWT via `/api/auth/login` and update `claude_desktop_config.json`, then restart Claude Desktop.

---

## Live Integration Test (manual)

1. Run FastAPI locally with your user (`APP_USER_ID=jai` in `.env`)
2. Seed 3 tasks via the dashboard at `http://localhost:3000`
3. Configure and restart Claude Desktop with the MCP config above
4. Ask: *"What are my pending tasks?"* → `list_tasks` fires
5. Ask: *"Mark the first one done."* → `complete_task` fires
6. Ask: *"Find anything related to insurance."* → `find_similar_tasks` fires
7. Open the dashboard — confirm task state matches Claude's responses
