# Nudge / Project Mirror — System Overview

> Last updated: 2026-04-10
> Current phase: Phase 1 (Core stabilization — in progress)

---

## 1. What This System Is

A **personal AI-first productivity operating system**. The dashboard is the primary interface where all decisions happen — tasks, goals, nudges, and feedback. Notion is the persistence and integration layer, not the control center.

It is **not** a Notion companion, chatbot, or passive viewer. It is an active system that manages tasks and goals directly, delivers behavioral nudges, and learns from user responses.

Core loop:
```
Observe → Understand → Decide → Act → Learn
```

### Product Direction (updated 2026-04-12)

**Before:** "AI layer on top of tools you already use" — Notion was the control center, UI was passive.

**Now:** "AI-first productivity system with its own interface" — Dashboard is the control center, Notion is storage.

| Role | Before | Now |
|------|--------|-----|
| Dashboard | Read-only viewer | Write-enabled command center |
| Notion | Source of truth | Persistence + integration layer |
| Nudge system | Layer on top of Notion | Behavioral layer on top of the dashboard |

The user should never need to open Notion. Everything — creating tasks, updating status, managing goals, reviewing nudges — happens in the dashboard.

| Stage | Module |
|-------|--------|
| Observe | `input/` — Notion + Google Calendar connectors (read) |
| Write | `output/` — Notion writer (write-back from dashboard actions) ← NEW |
| Store | `Memory/` — SQLite + ChromaDB per user (operational source of truth) |
| Understand | `llm_module/` — Gemini LLM (or mock) |
| Decide | `Remind/` — Rule-based nudge engine |
| Act | `Orchestrator/` + `api/` — Scheduler + REST API |
| Learn | `Memory/` — Action logging + pattern storage |

---

## 2. Actual Folder Structure

```
Nudge/
├── Memory/                    # Storage + context building
│   ├── memory.py              # build_user_context(), log_action(), ingest()
│   ├── models.py              # Pydantic UserContext model
│   ├── schema.sql             # SQLite schema (tasks, goals, events, contacts, actions)
│   └── tests/
│
├── llm_module/llm_module/     # LLM inference layer
│   ├── __init__.py            # generate_insight(context, mode) — public API
│   ├── llm_client.py          # Gemini API call (real mode)
│   ├── mock_client.py         # Deterministic mock (no API call)
│   ├── prompt.py              # build_prompt(context)
│   ├── schemas.py             # UserContext + Insight TypedDicts + REQUIRED_FIELDS
│   └── validator.py           # parse_and_validate(raw_json)
│
├── Remind/                    # Nudge generation
│   ├── nudge_engine.py        # generate_nudges(insight, context, history, prefs)
│   └── test_nudge_engine.py
│
├── Orchestrator/              # Pipeline scheduler
│   ├── orchestrator.py        # run_job(), run_scheduler()
│   └── state.py               # In-memory per-user state (nudge counts, history)
│
├── input/                     # Data ingestion from external sources (read)
│   ├── config.py              # Dot-notation reader over settings.yaml
│   ├── ingestion_service.py   # IngestionService.ingest_all(user_id)
│   ├── connectors/
│   │   ├── tasks_connector.py      # Notion Tasks DB
│   │   ├── goals_connector.py      # Notion Goals DB
│   │   ├── contacts_connector.py   # Notion Contacts DB
│   │   └── calendar_connector.py   # Google Calendar (with token auto-refresh)
│   └── normalizers/
│       ├── task_normalizer.py
│       ├── goal_normalizer.py
│       ├── contact_normalizer.py
│       └── calendar_normalizer.py
│
├── output/                    # Write-back to Notion (NEW — not yet built)
│   └── notion_writer.py       # create_task(), update_task(), update_status()
│
├── api/                       # FastAPI REST layer
│   ├── main.py                # App setup, CORS (restricted to FRONTEND_URL), routers
│   ├── auth.py                # JWT create/decode (HS256, 24h TTL)
│   ├── dependencies.py        # sys.path bridge + get_current_user() FastAPI dep
│   ├── routes/
│   │   ├── auth.py            # POST /api/auth/login, GET /api/auth/me
│   │   ├── context.py         # GET /api/context
│   │   ├── insight.py         # GET /api/insight
│   │   ├── nudges.py          # GET /api/nudges
│   │   ├── actions.py         # POST /api/log-action
│   │   ├── sync.py            # POST /api/sync
│   │   └── system.py          # POST /api/run-cycle, GET /api/health
│   ├── services/
│   │   └── orchestrator_service.py  # Bridge: routes → core modules
│   └── schemas/
│       └── base.py            # Pydantic request/response models
│
├── Dashboard/                 # Next.js frontend
│   ├── app/
│   │   ├── page.tsx           # Main dashboard (polling: nudges/10s, context/30s, insight/60s)
│   │   └── login/page.tsx     # JWT login form
│   ├── lib/
│   │   ├── api.ts             # All Axios calls with auth headers
│   │   └── auth.ts            # getToken/setToken/clearToken (localStorage)
│   └── types/index.ts         # TypeScript types matching backend exactly
│
├── main.py                    # CLI entry point (dry-run pipeline)
├── settings.yaml              # Storage paths, Notion DB IDs, integration config
└── .env                       # API keys + secrets (not committed)
```

---

## 3. Data Contracts

### UserContext (Memory → LLM)

```json
{
  "goals":             ["string"],
  "tasks":             [{"id": "", "title": "", "status": "pending|overdue|completed", "due_date": ""}],
  "recent_actions":    ["string"],
  "behavior_patterns": ["string"],
  "daily_summary":     "string"
}
```

### Insight (LLM → Nudge Engine)

```json
{
  "insight_id":        "uuid",
  "summary":           "string",
  "key_observations":  ["string"],
  "goal_alignment":    "string",
  "behavior_flags":    ["string"],
  "opportunity_areas": ["string"],
  "decision_signals": {
    "needs_activation":  false,
    "needs_correction":  false,
    "goal_at_risk":      false,
    "has_overdue_tasks": false
  }
}
```

### Nudge (Nudge Engine → API → Frontend)

```json
{
  "type":     "correction|activation|strategic|reminder|reflection",
  "message":  "string",
  "priority": "high|medium|low",
  "timing":   "immediate|scheduled"
}
```

---

## 4. Pipeline: How a Nudge Gets Generated

```
1. POST /api/sync
   └── IngestionService.ingest_all(user_id)
       ├── TaskConnector     → Notion Tasks DB   → normalize → Memory.ingest("tasks")
       ├── GoalsConnector    → Notion Goals DB   → normalize → Memory.ingest("goals")
       ├── ContactsConnector → Notion Contacts DB → normalize → Memory.ingest("contacts")
       └── CalendarConnector → Google Calendar   → normalize → Memory.ingest("events")

2. GET /api/nudges
   └── orchestrator_service.get_nudges(user_id, mode)
       ├── memory.build_user_context(user_id)   → UserContext (Pydantic)
       ├── _build_llm_context(raw)              → flat dict for LLM
       ├── generate_insight(llm_dict, mode)     → Insight with decision_signals
       └── nudge_engine.generate_nudges(...)    → list of nudges (max 2)
```

Nudge generation rules (decision signals → nudge types):
- `needs_correction` or `has_overdue_tasks` → `correction` nudge (high priority)
- `goal_at_risk` → `strategic` nudge (medium priority)
- `needs_activation` → `activation` nudge (low priority)
- `evening_reflection` in `behavior_flags` → `reflection` nudge (low priority)

Rate limits: max 3 nudges/day, max 2 per call, deduped against recent nudge types.

---

## 5. Orchestrator Jobs

The orchestrator runs three scheduled jobs (and one on-demand):

| Job | Time | What it does |
|-----|------|-------------|
| `morning` | 07:00 | Full pipeline: context → insight → planning nudges |
| `midday` | 12:00 | Inactivity check → activation nudge (synthetic insight, no LLM call) |
| `evening` | 19:00 | Full pipeline → reflection nudges (strictness 0.4) |
| `event` | on-demand | Full pipeline triggered by an external event |

Run the scheduler:
```bash
python -c "from Orchestrator.orchestrator import run_scheduler; run_scheduler('jai', mode='mock')"
```

Trigger a single job on-demand via API:
```bash
curl -X POST http://localhost:8000/api/run-cycle \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"job_type": "midday", "mode": "mock"}'
```

---

## 6. Authentication

JWT-based. Token stored in browser `localStorage` under key `auth_token`.

- Login: `POST /api/auth/login` with `{"username": "jai", "password": "<APP_PASSWORD>"}`
- All other routes require `Authorization: Bearer <token>`
- Token TTL: 24 hours
- Credentials set in `.env`: `APP_USER_ID`, `APP_PASSWORD`, `JWT_SECRET_KEY`

---

## 7. Running the System

```bash
# Backend (from Nudge/ root)
uvicorn api.main:app --reload
# → http://localhost:8000  |  docs at /docs

# Frontend (from Dashboard/)
npm run dev
# → http://localhost:3000

# CLI dry-run (mock LLM, no server needed)
python main.py

# Real Gemini mode
python main.py --real
```

---

## 8. Current State (as of 2026-04-10)

### What is fully working
- All 4 connectors fetch live data from Notion and Google Calendar
- Task overdue detection: tasks past their due date are automatically flagged `overdue` (not dependent on Notion status field)
- Memory upserts: re-syncing updates existing task statuses correctly
- Full nudge pipeline fires correctly: 6 of 8 Notion tasks are overdue → `needs_correction = True` → correction nudge generated
- JWT auth, CORS restriction, all API routes
- Dashboard: login, polling, nudge display, sync button, action buttons (acknowledge/snooze/ignore)

### What is in progress
- Auto-sync: user must currently call `POST /api/sync` manually before nudges reflect fresh data
- Observability: no structured per-pipeline-step logging yet

### What is not yet built
- Nudge messages don't reference specific task names (generic templates only)
- No push notifications (user must open dashboard)
- Feedback loop: acknowledge/ignore signals are logged but not used to adjust future nudges
- Pattern detection: behavior_patterns is always empty (pattern engine not yet wired)
- Real LLM mode not tested end-to-end from the frontend (api.ts uses `mode: "mock"`)

---

## 9. Known Constraints

| Constraint | Detail |
|-----------|--------|
| State is in-memory | `Orchestrator/state.py` resets on server restart. Nudge counts, rate limits, and history are all lost. This is the most critical gap. |
| User isolation is correct | Each user gets a separate SQLite DB via `db.get_connection(user_id)`. JWT `sub` claim carries `user_id`. Per-user isolation is working. |
| Single login | Only one user can log in (`APP_USER_ID` / `APP_PASSWORD` in `.env`). Sufficient for personal use; extending requires a users table and hashed passwords. |
| Rate limiting is logic-only | `nudge_engine.py` enforces daily limits and dedup correctly, but the counters live in `state.py` — they reset on restart, so the limit only holds within a session. |
| Calendar returns 0 events | Primary Google Calendar has no events today. Connector and token refresh are working correctly. |
| Contacts are test data | Two placeholder contacts in Notion, no real `Last Contact` dates. |

---

## 10. Product Roadmap

> **Direction updated 2026-04-12.** The system has shifted from "AI layer on top of Notion" to "AI-first productivity OS with its own interface." Roadmap phases have been reordered accordingly.

---

### ✅ Phase 0 — Core Infrastructure (Complete)

All foundational work done:
- Persisted orchestrator state (SQLite, survives restarts)
- Auto-scheduler (morning/midday/evening jobs fire automatically)
- Auto-sync background thread (every 15 min)
- Full nudge pipeline: context → LLM → nudge bank → delivery
- JWT auth, CORS, all API routes
- Telegram delivery with inline buttons + callback logging
- Evaluation endpoint (`GET /api/evaluation/today`)
- TEST_MODE for accelerated local testing

---

### 🔄 Phase 1 — Dashboard as Control Center (Current Priority)

Make the dashboard write-enabled. The user should never need to open Notion.

**1. Task write APIs**
```
POST   /api/tasks          — create task
PATCH  /api/tasks/{id}     — update title, status, due date
DELETE /api/tasks/{id}     — delete task
```
Flow: UI → API → SQLite first (non-blocking) → async Notion write-back.

**2. Goal write APIs**
```
POST   /api/goals          — create goal
PATCH  /api/goals/{id}     — update title, priority
```

**3. Notion write-back module (`output/notion_writer.py`)**
- `create_task(title, due_date, status)` → Notion Tasks DB
- `update_task(notion_id, fields)` → Notion page update
- `update_status(notion_id, status)` → Notion status field
- Runs async after SQLite write — UI never waits on Notion API
- SQLite is the operational source of truth; Notion is eventual consistency

**4. Sync conflict strategy**
- Add `last_modified TIMESTAMP` and `source TEXT` ("notion" or "local") to `tasks` and `goals` tables
- Rule: latest `last_modified` wins on conflict; prefer local if timestamps are equal

**5. Editable task UI**
- Inline status toggle (pending → completed)
- Inline due date picker
- Quick-add input: type "Finish report by 5pm" → parsed into title + due date
- Overdue tasks highlighted prominently at top of task list

Exit: User creates a task in the dashboard, it appears in Notion within seconds, and the nudge system picks it up on next sync.

---

### Phase 2 — Better Nudges

**6. Context-aware nudge messages**
Nudge text must reference actual task names and counts:
> "7 tasks are overdue — oldest since Feb 2026. Start with 'Verify Project Mirror write pipeline'."
Requires passing task titles and due dates into the nudge message template.

**7. Nudge preferences panel**
- Configurable nudge times (replace hardcoded 07:00/12:00/19:00)
- Max nudges per day
- Strictness slider (supportive ↔ strict)
- Store in `user_preferences` table, serve via `GET/POST /api/preferences`

Exit: A nudge names a real task and feels written for you. You can control when and how many nudges you receive.

---

### Phase 3 — UI Polish

**8. Today view** — tasks due today + overdue (highlighted) + next 3 upcoming
**9. Nudge history** — what was sent today and what action was taken
**10. Sync status** — "Last synced: 2 min ago"
**11. Empty/onboarding state** — clear guidance when no data is connected

Exit: The dashboard tells the full story of your day without needing to look elsewhere.

---

### Phase 4 — Notifications (Partially Done)

✅ Telegram delivery with action buttons — complete
- Browser push notifications (service worker) — not yet built
- Mobile: React Native wrapper — long term

Exit: Nudges reach you on every surface without opening the dashboard.

---

### Phase 5 — Intelligence

**12. Pattern detection** — derive `behavior_patterns` from `user_actions`: repeated delays, inactivity windows, task types never completed. Feed into LLM context.
**13. Feedback-driven personalization** — adjust `strictness` and nudge type frequency from acknowledged/ignored signals.
**14. Real LLM as default** — prompt-tune based on observed Gemini output variability.

Exit: The system knows your behavior patterns and nudges differently based on them.

---

## Sync Architecture (Updated)

```
Dashboard action (create/edit/delete)
    │
    ▼
SQLite (writes immediately — source of truth)
    │
    ▼ async, non-blocking
Notion (eventual consistency — persistence layer)

Notion (external changes, e.g. from mobile)
    │
    ▼ every 15 min
SQLite (sync pulls — last_modified wins on conflict)
```

---

## What This System Is

- A **daily command center**: tasks, goals, nudges — all managed from one interface
- A **behavioral operating system**: observes patterns, intervenes at the right moment
- **Notion-backed**: changes sync to Notion for mobile access and backup, but the dashboard is the primary interface

## What This System Is Not

- Not a passive Notion viewer — the dashboard is write-enabled
- Not a chatbot — it doesn't respond to queries
- Not a full task manager — complexity is limited to what the nudge system needs
