# Nudge / Project Mirror — Handover Document

> For: New joinee or incoming project head
> Last updated: 2026-04-12
> Current phase: Phase 1 complete (control center + write APIs)

---

## 1. What Is This System?

**Nudge** (also called Project Mirror) is a personal AI-first productivity operating system. The dashboard is the primary interface — tasks and goals are created, edited, and managed there. Notion is the persistence and integration layer, not the control center. The system observes behavior, generates insights via Gemini LLM once per day, and delivers targeted nudges via Telegram and the dashboard.

It is **not** a Notion companion or passive viewer. The dashboard is write-enabled.

```
Dashboard (create/edit) → SQLite → async Notion write-back
Notion / GCal (sync every 15 min) → SQLite → Gemini LLM → Nudge Engine → Telegram + Dashboard
```

The system is currently used by one person (Jai) as a personal tool. The architecture is designed for per-user isolation — each user gets a separate SQLite database.

---

## 2. Read This First

| Document | What it covers |
|----------|---------------|
| [Overview.md](Overview.md) | Full system overview: architecture, data contracts, pipeline walkthrough, current state, known constraints, and the product roadmap |
| [CLAUDE.md](CLAUDE.md) | How to run the system, run tests, module layout, and key dependencies |
| [settings.yaml](settings.yaml) | All configuration: storage paths, Notion DB IDs, Google integration settings |
| [.env](.env) | API keys and secrets — never commit this |

**Start with Overview.md. Everything else is detail.**

---

## 3. How to Run It

### Prerequisites

```bash
pip install -r requirements.txt   # Python dependencies
cd Dashboard && npm install        # Frontend dependencies
```

Ensure `.env` has:
- `GEMINI_API_KEY` — from Google AI Studio
- `NOTION_API_KEY` — from Notion integrations page
- `JWT_SECRET_KEY` — any strong random string
- `APP_USER_ID` + `APP_PASSWORD` — login credentials for the dashboard
- `FRONTEND_URL` — `http://localhost:3000` for local dev

### Start the system

```bash
# Terminal 1 — Backend (from Nudge/ root)
uvicorn api.main:app --reload
# Starts at http://localhost:8000
# Auto-starts: sync loop (every 15 min) + scheduler (morning/midday/evening jobs)

# Terminal 2 — Frontend (from Nudge/Dashboard/)
npm run dev
# Starts at http://localhost:3000
```

### Verify it's working

1. Open `http://localhost:3000` — log in with `APP_USER_ID` / `APP_PASSWORD`
2. Dashboard should show tasks (synced from Notion) and a nudge within 10 seconds
3. API docs at `http://localhost:8000/docs`

### CLI dry-run (no server needed)

```bash
python main.py           # mock LLM, no API calls
python main.py --real    # real Gemini
```

---

## 4. Module Map — What Lives Where

### Backend

| Directory | What it does | Key file to read first |
|-----------|-------------|----------------------|
| `Memory/` | Per-user storage. Reads/writes SQLite and ChromaDB. Builds `UserContext`. | `memory.py` |
| `llm_module/llm_module/` | Calls Gemini to convert `UserContext` → `Insight`. Supports mock mode. | `__init__.py` |
| `Remind/` | Rule-based nudge engine. Takes `Insight` → outputs nudges. | `nudge_engine.py` |
| `Orchestrator/` | Scheduler (morning/midday/evening jobs) and persisted state. | `orchestrator.py`, `state.py` |
| `input/` | Data connectors for Notion (tasks, goals, contacts) and Google Calendar. | `ingestion_service.py` |
| `api/` | FastAPI REST layer. Thin wrapper over core modules. | `main.py`, `services/orchestrator_service.py` |
| `Dashboard/` | Next.js frontend. All client-side, no SSR. | `app/page.tsx`, `lib/api.ts` |

### Configuration files

| File | Purpose |
|------|---------|
| `settings.yaml` | Storage paths, Notion DB IDs, Google scopes, sync settings |
| `.env` | API keys and secrets |
| `Memory/schema.sql` | SQLite schema for all tables |
| `Dashboard/lib/api.ts` | All frontend API calls with auth headers |
| `Dashboard/types/index.ts` | TypeScript types — must match backend exactly |

### Contract and spec docs (one per module)

Each module has its own `CONTRACT.md` and `SPEC.md`. These define the input/output interface for that module. If you change a module's behavior, check its contract first.

| Module | Contract | Spec |
|--------|----------|------|
| Memory | `Memory/CONTRACT.md` | `Memory/SPEC.md` |
| LLM | `llm_module/CONTRACT.md` | `llm_module/SPEC.md` |
| Nudge Engine | `Remind/CONTRACT.md` | `Remind/SPEC.md` |
| Orchestrator | `Orchestrator/CONTRACT.md` | `Orchestrator/SPEC.md` |
| Input | `input/CONTRACT.md` | `input/SPEC.md` |
| API | `api/CLAUDE.md` | `api/IMPLEMENT.md` |
| Dashboard | `Dashboard/FRONTEND_BACKEND_COMMS.md` | `Dashboard/IMPLEMENTATION.md` |

---

## 5. Data Flow (End to End)

```
Every 15 minutes (background thread):
  input/ingestion_service.py → Notion + GCal APIs → Memory/memory.py → SQLite

Once a day at 07:00 (scheduler):
  orchestrator.py → memory.build_user_context()
                  → llm_module.generate_insight()   ← ONE Gemini call/day
                  → state.store_insight_cache()      ← cached in SQLite
                  → nudge_engine._pick_message()     ← 5 nudges pre-generated
                  → state.store_nudge_bank()         ← stored in nudge_bank table

All day (frontend polling every 10s):
  GET /api/nudges → orchestrator_service.get_nudges()
                  → state.get_nudge_bank()           ← zero LLM calls
                  → selects by signal + dedup
                  → state.record_nudges()            ← logged to nudge_log

User action (acknowledge / snooze / ignore):
  POST /api/log-action → memory.log_action() → user_actions table
```

### SQLite tables (per-user DB at `Memory/data/{user_id}/mirror.db`)

| Table | What it stores |
|-------|---------------|
| `tasks` | Synced from Notion — title, status, due_date |
| `goals` | Synced from Notion — title, priority |
| `events` | Synced from Google Calendar |
| `contacts` | Synced from Notion contacts DB |
| `user_actions` | All user interactions logged via `POST /api/log-action` |
| `nudge_log` | Every nudge sent — used for daily rate limiting and dedup |
| `nudge_bank` | Today's pre-generated nudge pool (5 types, refreshed each morning) |
| `orchestrator_state` | Key-value: last_run, last_run_job, cached insight + date |
| `behavior_patterns` | Not yet populated — reserved for Phase 5 pattern detection |

---

## 6. API Reference

Base URL: `http://localhost:8000/api`

All routes except login require `Authorization: Bearer <token>`.

| Method | Route | What it does |
|--------|-------|-------------|
| POST | `/auth/login` | Login with `user_id` + `password`, returns JWT |
| GET | `/auth/me` | Returns `user_id` from token |
| GET | `/context` | User's current context from memory |
| GET | `/insight?mode=real` | Today's cached insight (no LLM call if cached) |
| GET | `/nudges?mode=real` | Today's nudges from bank (no LLM call) |
| POST | `/log-action` | Log a user action (acknowledged, snoozed, ignored) |
| POST | `/sync` | Manual trigger of `ingest_all` (auto-runs every 15 min) |
| POST | `/run-cycle` | Trigger a specific job: `morning`, `midday`, `evening`, `event` |
| GET | `/` | Health check |

Full interactive docs at `http://localhost:8000/docs`.

---

## 7. LLM Usage and Rate Limiting

**Important:** The system is on Gemini's free tier.

**How it's managed:**
- LLM is called **once per day** during the morning job
- The insight and a bank of 5 nudges are cached in SQLite
- All subsequent API calls (`/insight`, `/nudges`) serve from the cache — zero LLM calls
- If the morning LLM call fails (503 overload, 429 rate limit), mock mode is used as fallback
- Retries: 3 attempts with 5s and 15s backoff between attempts

**To change LLM mode:**
- `LLM_MODE=mock` in `.env` — never calls Gemini, uses deterministic mock
- `LLM_MODE=real` in `.env` — uses Gemini 2.5 Flash

**Model:** `gemini-2.5-flash` (set in `llm_module/llm_module/llm_client.py`)

---

## 8. Nudge System Explained

Nudges are generated by `Remind/nudge_engine.py`. There are 5 types:

| Type | When it fires | Priority |
|------|--------------|---------|
| `correction` | Overdue tasks detected | High |
| `strategic` | Goals at risk | Medium |
| `reminder` | Repeated delays | Medium |
| `activation` | No recent activity | Low |
| `reflection` | Evening job / evening hours | Low |

**Rate limits:**
- Max 5 nudges per day
- Max 2 per API call
- No duplicate types within the same day
- Types are served in priority order from the bank; signal-matched types go first

**Strictness:** Controls the tone of messages (0.0 = all supportive, 1.0 = all strict). Default 0.7. Evening jobs use 0.4.

---

## 9. Frontend

The dashboard is in `Dashboard/`. All pages are client components — no SSR.

**Login flow:** `POST /api/auth/login` → JWT stored in `localStorage` under key `auth_token`.

**Polling intervals (in `Dashboard/app/page.tsx`):**
- Nudges: every 10 seconds
- Context: every 30 seconds
- Insight: every 60 seconds

**Key files:**

| File | Purpose |
|------|---------|
| `Dashboard/app/page.tsx` | Main dashboard — all state, polling, nudge action handling |
| `Dashboard/app/login/page.tsx` | Login form |
| `Dashboard/lib/api.ts` | All API calls — change `mode` param here to switch mock/real |
| `Dashboard/lib/auth.ts` | JWT get/set/clear from localStorage |
| `Dashboard/types/index.ts` | TypeScript types — must match backend schema exactly |

**If you change a backend response shape**, update `Dashboard/types/index.ts` first, then the consuming component.

---

## 10. Running Tests

```bash
# Memory module tests
cd Memory && python -m pytest tests/

# Orchestrator tests
cd Orchestrator && python -m pytest tests/

# LLM module tests
cd llm_module && python -m pytest tests/

# Nudge engine tests
python -m pytest Remind/test_nudge_engine.py

# Full API integration tests (requires running server)
python -X utf8 tests/test_api_full.py
```

---

## 11. Known Constraints and Gotchas

**Module imports:** Modules are not installed as packages. `sys.path` is patched at runtime in `main.py`, `api/dependencies.py`, and `Orchestrator/orchestrator.py`. When adding cross-module imports, follow this pattern — don't use relative imports across module boundaries.

**Notion task overdue detection:** The connector auto-flags tasks as `overdue` if their due date has passed and status is still pending. It does NOT rely on Notion's status field being set to "overdue". This is intentional — users rarely update Notion status manually.

**`INSERT OR IGNORE` was a bug:** Early versions used `INSERT OR IGNORE` for tasks, so re-syncing never updated statuses. This is now fixed with `ON CONFLICT DO UPDATE` in `Memory/memory.py`.

**State used to be in-memory:** `Orchestrator/state.py` originally stored everything in a Python dict — resetting on every server restart. It now writes to SQLite. If you see stale rate limit behavior, check `nudge_log` and `orchestrator_state` tables.

**Single user:** Only one `APP_USER_ID` can log in. The architecture supports multiple users (separate DBs), but the auth layer only validates one hardcoded user. Extending to multi-user requires a `users` table and hashed passwords.

**Calendar returns 0 events:** This is normal — the connector fetches only today's events. If your Google Calendar has no events today, the array is empty. Connector and token refresh are working correctly.

**Gemini 503s:** Gemini 2.5 Flash experiences intermittent high-demand errors. The retry logic handles this (3 attempts, 5s/15s backoff). If all retries fail, mock insight is used as fallback.

**Hot reload crashes:** `uvicorn --reload` sometimes crashes when multiple files change rapidly. Restart the server if you see connection refused errors. This is a development inconvenience, not a production issue.

---

## 12. What Has Been Built (Phase 0 Complete)

- All 4 data connectors (Notion tasks, goals, contacts + Google Calendar) fetching live data
- Per-user SQLite memory with correct upsert behavior on re-sync
- Auto-sync background thread (every 15 min, runs on server startup)
- Auto-scheduler background thread (fires morning/midday/evening jobs at scheduled times)
- Full LLM pipeline: `UserContext → Gemini → Insight → decision signals → nudges`
- Daily nudge bank: 1 LLM call/day, 5 pre-generated nudges served from SQLite all day
- Insight cache: served from DB after morning job, no repeated LLM calls
- JWT authentication on all API routes
- CORS restricted to configured frontend origin
- Persisted state: nudge history, rate limits, and last-run metadata survive server restarts
- Structured observability logs at each pipeline stage
- Next.js dashboard: login, nudge display, sync, action buttons, polling
- **Telegram bot**: proactive nudge delivery with ✅/⏰/❌ inline buttons, long-polling, callback logging, button auto-dismiss after response
- **Evaluation endpoint**: `GET /api/evaluation/today` — nudges sent, response rate, overdue delta
- **TEST_MODE**: scheduler fires every N minutes for rapid local testing

---

## 13. What Comes Next

See `Overview.md` section 10 for the full roadmap. **Direction updated 2026-04-12** — system has shifted from "AI layer on top of Notion" to "AI-first productivity OS with its own interface."

**Phase 1 — Dashboard as Control Center (current priority)**
- Write APIs: `POST/PATCH/DELETE /api/tasks`, `POST/PATCH /api/goals`
- `output/notion_writer.py` — async write-back to Notion after SQLite updates
- Editable task UI: inline status toggle, due date picker, quick-add input
- Sync conflict strategy: `last_modified` + `source` columns, latest wins

**Phase 2 — Better Nudges**
- Nudge messages reference actual task names and counts
- User preferences panel (nudge times, max/day, strictness)

**Phase 3 — UI Polish**
- Today view, nudge history, sync status indicator

**Phase 4 — Notifications**
- Browser push notifications (Telegram already done)

**Phase 5 — Intelligence**
- Pattern detection from action history
- Feedback-driven personalization

---

## 14. Who to Contact

This system was built by Jai. All technical decisions, architectural choices, and implementation context are documented in:
- `Overview.md` — system-level decisions
- `CLAUDE.md` — development conventions
- Each module's `CONTRACT.md` and `SPEC.md` — interface decisions
- `Orchestrator/IMPLEMENTATION_GUIDE.md` — scheduler design rationale
- `Dashboard/FRONTEND_BACKEND_COMMS.md` — API contract with frontend
