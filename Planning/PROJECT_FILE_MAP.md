# 📍 Project Nudge — Complete File Map

> Use this as your compass. Every file, what it does, and where to start building.

---

## Project Root

```
C:\Users\jaiad\Personal_Work_Related\Personal Projects\Nudge\
```

---

## 🔑 Read These First (in order)

| # | File | Why |
|---|------|-----|
| 1 | [CLAUDE.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/CLAUDE.md) | Agent instructions — project overview, how to run, module layout, upcoming WebSocket architecture |
| 2 | [HANDOVER.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/HANDOVER.md) | Original spec — objectives, sync loop design, reusable assets, directory structure |
| 3 | [remote_agent_spec.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/remote_agent_spec.md) | User-facing project specification |
| 4 | [Planning/WEBSOCKET_RELAY_ARCHITECTURE.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/WEBSOCKET_RELAY_ARCHITECTURE.md) | **⭐ The next thing to build** — dual-path WebSocket relay design, code sketches, implementation order |
| 5 | [Planning/SYSTEM_STATE.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/SYSTEM_STATE.md) | Full inventory of what exists, what works, and what's empty |

---

## 🤖 System A — Bot (Telegram Accountability Agent)

> **This is the implementation directory for the WebSocket relay work.**

```
bot/
├── cloud_bot.py          ← MODIFY: Add WebSocket server + prefix routing
├── local_sync.py         ← MODIFY: Add WebSocket client (auto-reconnect)
├── command_handlers.py   ← NO CHANGE: Already modular, works for both paths
├── table_parser.py       ← NO CHANGE: Markdown table updater for plan
├── command_queue.json    ← WILL BECOME: Fallback-only (currently primary)
├── run_sync.bat          ← Windows Task Scheduler trigger
├── requirements.txt      ← MODIFY: Add `websockets` dependency
├── .env                  ← Secrets (DO NOT COMMIT)
└── .env.example          ← MODIFY: Add CLOUD_WS_URL, WS_AUTH_TOKEN
```

### Key files to understand:

| File | Lines | What it does |
|------|-------|-------------|
| [cloud_bot.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/cloud_bot.py) | 435 | The cloud brain. Telegram polling → Gemini intent parsing → Git commit/push. Handles `/start`, `/status`, message routing, Sunday audit (9 PM cron), Pass/Fail callback buttons, health check HTTP server for Render. **This is where you add the WebSocket server and `>` prefix routing.** |
| [local_sync.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/local_sync.py) | 229 | Laptop daemon. Runs on Windows login. `git fetch` → pull if behind → copies plan to `Next_Move/` → reads `command_queue.json` → dispatches commands → clears queue → pushes. **This is where you add the WebSocket client.** |
| [command_handlers.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/command_handlers.py) | 134 | Modular command dispatcher. `dispatch_command()` routes to: `handle_screenshot()` (PIL/pyautogui), `handle_query_db()` (SQLite full-text search across all tables), `handle_shell_command()` (whitelisted: git status, git log, run tests). **Already works for WebSocket path — no changes needed.** |
| [table_parser.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/table_parser.py) | 157 | Parses and updates the weekly audit markdown table in `complex_accountability_plan.md`. Handles columns: leetcode_solved, leetcode_contest, study_hours, git_commits_cert, notes, Status. |

---

## 🧠 System B — App (AI Nudge Engine)

> Separate from the bot. A full-stack behavioral feedback system.

```
app/
├── main.py                    ← CLI entry point (dry-run / real mode)
├── notification_service.py    ← Dual delivery: Web Push + Telegram fallback
│
├── Memory/                    ← Data layer
│   ├── db.py                  ← SQLite per-user isolation
│   ├── memory.py              ← 26K lines of CRUD + context building
│   ├── models.py              ← Pydantic models (UserContext, Task, Goal, etc.)
│   ├── schema.sql             ← 12-table schema
│   └── vector_db.py           ← ChromaDB vector store for semantic search
│
├── llm_module/                ← Gemini 2.5 Flash inference
│   └── llm_module/            ← generate_insight(), mock mode, retry logic
│
├── Remind/                    ← Rule-based nudge engine
│   └── (nudge generation, 6 types, rate limiting, strictness)
│
├── Orchestrator/              ← Scheduler + pipeline
│   ├── orchestrator.py        ← 663 lines — morning/midday/evening/event jobs
│   └── state.py               ← 245 lines — insight cache, last-run tracking
│
├── input/                     ← Google Calendar + Contacts ingestion
│
├── api/                       ← FastAPI REST layer
│   ├── main.py                ← App startup, CORS, background threads
│   ├── auth.py                ← JWT authentication
│   ├── dependencies.py        ← Shared deps, sys.path patching
│   └── routes/                ← 14 route modules (see below)
│
├── scripts/                   ← VAPID key generation
└── tests/                     ← Integration tests
```

### API Routes (14 modules):

| Route file | Endpoints | Purpose |
|-----------|-----------|---------|
| [auth.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/auth.py) | `POST /api/auth/login`, `GET /api/auth/me` | JWT login |
| [tasks.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/tasks.py) | `POST/GET/PATCH/DELETE /api/tasks` | Full task CRUD with nudge config |
| [goals.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/goals.py) | `POST/GET/PATCH/DELETE /api/goals` | Goal CRUD |
| [context.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/context.py) | `GET /api/context` | Full UserContext snapshot |
| [insight.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/insight.py) | `GET /api/insight` | Today's cached LLM insight |
| [nudges.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/nudges.py) | `GET /api/nudges` | Nudges from daily bank |
| [actions.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/actions.py) | `POST /api/log-action` | Log ack/snooze/ignore |
| [preferences.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/preferences.py) | `GET/POST /api/preferences` | Nudge schedule, strictness |
| [sync.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/sync.py) | `POST /api/sync` | Manual Google sync trigger |
| [system.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/system.py) | `POST /api/run-cycle` | Trigger job cycles |
| [push.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/push.py) | VAPID key, subscribe/unsubscribe/test | Web Push management |
| [search.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/search.py) | `POST /api/search/tasks` | Semantic search via ChromaDB |
| [evaluation.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/evaluation.py) | `GET /api/evaluation/today` | Nudge effectiveness metrics |
| [telegram.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/app/api/routes/telegram.py) | Telegram webhook | Callback processing |

---

## 📊 Dashboard (Next.js PWA)

```
Dashboard/
├── app/
│   ├── page.tsx               ← Main dashboard, orchestrates all components
│   └── login/                 ← JWT login page
├── components/
│   ├── TaskList.tsx            ← 17K — Task CRUD, nudge config editor
│   ├── GoalList.tsx            ← Goal CRUD with priority groups
│   ├── SettingsPanel.tsx       ← Schedule times, strictness slider
│   ├── PushSetup.tsx           ← Service worker + VAPID subscription
│   ├── InsightCard.tsx         ← AI summary display
│   ├── NudgeCard.tsx           ← Ack/snooze/ignore buttons
│   └── CalendarView.tsx        ← Today's Google Calendar events
├── lib/                        ← Shared utilities
├── types/                      ← TypeScript type definitions
├── public/                     ← Static assets
├── package.json                ← Next.js deps
└── next.config.ts              ← Next.js config
```

---

## 🔌 MCP Server (Claude Desktop Integration)

```
mcp_servers/
├── __init__.py
└── tasks_server/
    ├── server.py              ← MCP server over stdio
    ├── tools.py               ← 11 tool definitions (list/get/create/update/delete tasks, search, context, goals, actions)
    ├── api_client.py          ← Async httpx client → FastAPI
    ├── schema_utils.py        ← Schema validation
    ├── README.md              ← Claude Desktop config setup guide
    └── tests/
```

---

## 📋 Planning & Docs

| File | What it is |
|------|-----------|
| [Planning/WEBSOCKET_RELAY_ARCHITECTURE.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/WEBSOCKET_RELAY_ARCHITECTURE.md) | **⭐ Build spec for the WebSocket relay** |
| [Planning/SYSTEM_STATE.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/SYSTEM_STATE.md) | What works, what's empty, full inventory |
| [Planning/REVISED_ARCHITECTURE.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/REVISED_ARCHITECTURE.md) | Architecture revision notes |
| [Planning/PHASE2_PLAN.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/PHASE2_PLAN.md) | Phase 2 planning |
| [Planning/DEPLOY_RAILWAY.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/DEPLOY_RAILWAY.md) | Railway deployment guide |
| [Planning/Initial_Vision.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/Initial_Vision.md) | Original vision |
| [Planning/MCP_TASKS_SERVER_WORKSTREAM.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/MCP_TASKS_SERVER_WORKSTREAM.md) | MCP implementation workstream |
| [Planning/MCP_SPIKE_FINDINGS.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/MCP_SPIKE_FINDINGS.md) | MCP research findings |
| [Planning/MCP_TOOL_EXTENSION_TEMPLATE.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/MCP_TOOL_EXTENSION_TEMPLATE.md) | Template for new MCP tools |

---

## 🧩 Other Root Files

| File | Purpose |
|------|---------|
| [complex_accountability_plan.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/complex_accountability_plan.md) | The actual 3-year career roadmap being tracked |
| [settings.yaml](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/settings.yaml) | Storage paths, Google sync config, logging |
| [requirements.txt](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/requirements.txt) | Python deps (app system) |
| [Procfile](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Procfile) | Render/Railway deploy command |
| [architecture.html](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/architecture.html) | Visual architecture diagram (open in browser) |
| [README.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/README.md) | Project readme |
| [implementation_plan.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/implementation_plan.md) | Original implementation task list |

---

## 🎯 Where to Start Building (WebSocket Relay)

### Implementation order:

| Step | File to modify | What to do |
|------|---------------|-----------|
| **1** | [bot/requirements.txt](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/requirements.txt) | Add `websockets` |
| **2** | [bot/.env.example](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/.env.example) | Add `CLOUD_WS_URL`, `WS_AUTH_TOKEN` |
| **3** | [bot/cloud_bot.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/cloud_bot.py) | Add WebSocket server + `>` prefix routing in message handler |
| **4** | [bot/local_sync.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/local_sync.py) | Add WebSocket client with auto-reconnect loop |
| **5** | [bot/cloud_bot.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/cloud_bot.py) | Add daemon online/offline status response |
| **6** | Test end-to-end | Send `> screenshot` from Telegram |
| **7** | [bot/cloud_bot.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/cloud_bot.py) | Add Git queue fallback when daemon is offline |

### Code sketches are in:
📄 [Planning/WEBSOCKET_RELAY_ARCHITECTURE.md § Section 3](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/Planning/WEBSOCKET_RELAY_ARCHITECTURE.md) — contains Python code for both the WebSocket server (cloud_bot) and client (local_sync)
