# Nudge — System State (as of 2026-04-14)

> What exists, what works, what's empty, and where every piece lives.
> Read this before planning any new work.

---

## 1. Module Inventory

### Memory/ — Data Layer
| Component | Status | Notes |
|-----------|--------|-------|
| `memory.py` | **Working** | Full CRUD for tasks, goals. `build_user_context()` returns Pydantic model with all entities. |
| `db.py` | **Working** | Per-user SQLite isolation at `data/{user_id}/mirror.db` |
| `vector_db.py` | **Working** | Per-user ChromaDB at `data/{user_id}/chroma/`. Embeds tasks, goals, contacts, events on ingest. |
| `models.py` | **Working** | Pydantic v2 models: Task, Goal, Event, Contact, BehaviorPattern, GoalAlignment, UserAction, UserContext |
| `schema.sql` | **Working** | 12 tables: users, goals, tasks, events, contacts, user_actions, behavior_patterns, goal_alignment, nudge_bank, nudge_log, orchestrator_state, user_preferences |
| `semantic_search()` | **Built, never used** | Searches across all ChromaDB collections for a user. No caller in the system. |
| `behavior_patterns` table | **Empty** | Schema exists, ingest path exists. Nothing writes patterns. |
| `goal_alignment` table | **Empty** | Schema exists, ingest path exists. Nothing computes alignments. |
| `push_subscriptions` table | **Working** | Web Push subscription storage, upsert by endpoint |

### llm_module/ — LLM Inference
| Component | Status | Notes |
|-----------|--------|-------|
| `generate_insight()` | **Working** | Context dict → Gemini 2.5 Flash → validated Insight dict |
| Mock mode | **Working** | Deterministic output, no API call |
| Retry logic | **Working** | 3 attempts with 5s/15s backoff, fallback to safe mock on total failure |
| `build_prompt()` | **Working** | Flat context dict → text prompt for Gemini |
| Prompt content | **Shallow** | Only gets today's tasks/goals/actions. No history, no patterns, no prior insights. |

### Remind/ — Nudge Engine
| Component | Status | Notes |
|-----------|--------|-------|
| `generate_nudges()` | **Working** | Insight + context + history + preferences → max 2 nudges per call |
| Task-aware messages | **Working (WS2)** | Correction nudges reference task titles. Activation nudges reference pending counts. |
| Custom nudge messages | **Working** | User-written `nudge_message` on a task is used for correction nudges |
| Decision signals | **Working** | needs_correction, needs_activation, goal_at_risk, has_overdue_tasks |
| Rate limiting | **Working** | Daily max, per-call max (2), type dedup against history |
| 6 nudge types | **Working** | correction (high), strategic (medium), productivity (medium), reminder (medium), activation (low), reflection (low) |

### Orchestrator/ — Scheduler + Pipeline
| Component | Status | Notes |
|-----------|--------|-------|
| `run_scheduler()` | **Working** | Blocking loop, fires morning/midday/evening jobs at user-configured times |
| `run_job()` | **Working** | Executes one job: context → insight → nudge → deliver |
| Per-task nudges | **Working** | Fires at exact `nudge_time`/`nudge_times` for each task, respects `nudge_days` |
| TEST_MODE | **Working** | Fires morning job every N minutes instead of clock-based |
| `state.py` | **Working** | Nudge bank, insight cache, nudge log, rate limits — all persisted to SQLite |
| Notification delivery | **Working (WS1)** | Calls `send_notification()` which tries Web Push then Telegram |

### input/ — Data Ingestion
| Component | Status | Notes |
|-----------|--------|-------|
| Google Calendar connector | **Working** | Fetches today's events via Google Calendar API |
| Google Contacts connector | **Working** | Fetches contacts via Google People API |
| Notion connectors | **Archived** | In `connectors/_archived/`. Not loaded. |
| Auto-sync | **Working** | Background thread runs `ingest_all()` every 15 minutes |

### api/ — FastAPI REST Layer
| Endpoint | Status | Notes |
|----------|--------|-------|
| `POST /api/auth/login` | **Working** | Returns JWT |
| `GET /api/auth/me` | **Working** | Returns user_id from token |
| `GET /api/context` | **Working** | Returns full UserContext (tasks, goals, events, contacts, actions, patterns) |
| `GET /api/insight` | **Working** | Returns today's cached insight (or generates if missing) |
| `GET /api/nudges` | **Working** | Returns nudges from bank, signal-matched |
| `POST /api/log-action` | **Working** | Logs acknowledged/snoozed/ignored |
| `POST /api/run-cycle` | **Working** | Trigger morning/midday/evening/event job |
| `POST /api/sync` | **Working** | Manual trigger of Google sync |
| `POST/PATCH/DELETE /api/tasks` | **Working** | Full task CRUD with nudge config fields |
| `POST/PATCH/DELETE /api/goals` | **Working (WS3)** | Full goal CRUD, delete nullifies task links |
| `GET/POST /api/preferences` | **Working** | Nudge schedule, limits, strictness |
| `GET /api/push/vapid-public-key` | **Working** | Returns VAPID public key |
| `POST /api/push/subscribe` | **Working** | Saves browser push subscription |
| `POST /api/push/unsubscribe` | **Working** | Removes subscription |
| `POST /api/push/test` | **Working** | Sends test push notification |
| `POST /api/sw-action` | **Working (WS4)** | Unauthenticated action logging from service worker |
| `GET /api/evaluation/today` | **Working** | Nudge effectiveness metrics |

### Dashboard/ — Next.js Frontend
| Component | Status | Notes |
|-----------|--------|-------|
| Login page | **Working** | JWT stored in localStorage |
| Task list + quick-add | **Working** | Overdue/pending/done groups, inline nudge config editor |
| Goal list + quick-add | **Working (WS3)** | Priority groups, edit/delete, linked task count |
| Task-to-goal linking | **Working (WS3)** | Dropdown in task editor |
| Calendar view | **Working** | Shows today's Google Calendar events |
| Insight card | **Working** | Displays AI summary and decision signals |
| Nudge cards | **Working** | Acknowledge/snooze/ignore buttons |
| Settings panel | **Working** | Morning/midday/evening times, max nudges, strictness |
| Push notification setup | **Working** | Service worker registration, VAPID subscription |
| Service worker actions | **Working (WS4)** | "Done"/"Later" buttons on notifications log to backend |
| PWA manifest + icons | **Working** | Installable on Android |

### notification_service.py — Delivery
| Component | Status | Notes |
|-----------|--------|-------|
| `send_notification()` | **Working (WS1)** | Web Push primary, Telegram fallback |
| `send_web_push_nudge()` | **Working** | pywebpush, handles expired subscriptions |
| `send_telegram_nudge()` | **Working** | Inline buttons: Acknowledge/Snooze/Ignore |
| Telegram polling | **Working** | Long-poll thread, callback handling, button dismiss |

---

## 2. Database Tables — What's Full vs. Empty

**Per-user SQLite at `Memory/data/{user_id}/mirror.db`**

| Table | Has Data | Written By | Read By |
|-------|----------|-----------|---------|
| `tasks` | Yes | Dashboard CRUD, (formerly Notion sync) | context, nudge engine, per-task scheduler |
| `goals` | Yes | Dashboard CRUD, (formerly Notion sync) | context, nudge engine |
| `events` | Yes (today only) | Google Calendar sync | context, LLM prompt |
| `contacts` | Yes | Google Contacts sync | context only — **never used downstream** |
| `user_actions` | Yes | log_action(), sw-action | **never analyzed** — only written, never read for intelligence |
| `behavior_patterns` | **EMPTY** | Nothing | context (would feed LLM if populated) |
| `goal_alignment` | **EMPTY** | Nothing | context (would feed LLM if populated) |
| `nudge_bank` | Yes | Morning job | /api/nudges |
| `nudge_log` | Yes | record_nudges() | Rate limiting, dedup, evaluation |
| `orchestrator_state` | Yes | Scheduler | Insight cache, last-run tracking |
| `user_preferences` | Yes | Settings panel | Scheduler times, strictness |
| `push_subscriptions` | Yes | PushSetup component | Web Push delivery |

---

## 3. Data Flow — What Actually Happens Today

```
STARTUP:
  api/main.py lifespan →
    Thread 1: sync loop (Google Cal + Contacts → SQLite every 15 min)
    Thread 2: scheduler (checks clock every 60s, fires jobs at configured times)
    Thread 3: telegram polling (listens for button callbacks)

MORNING JOB (07:00 default):
  memory.build_user_context(user_id) →
    reads: tasks, goals, events, contacts, user_actions (last 50), behavior_patterns, goal_alignment
    returns: UserContext pydantic model

  _context_to_llm_dict(context) →
    flattens to: goals (titles), tasks (id/title/status/due), recent_actions (types), behavior_patterns (descriptions), daily_summary
    NOTE: contacts, events, goal_alignments are DROPPED — never sent to LLM

  llm_module.generate_insight(context_dict, mode) →
    builds prompt → Gemini 2.5 Flash → parse + validate → Insight dict
    contains: summary, key_observations, behavior_flags, decision_signals

  state.store_insight_cache() → SQLite (served all day, no more LLM calls)

  _build_nudge_bank(insight, strictness, context) →
    generates 5 nudges (one per type) with task-aware messages
    state.store_nudge_bank() → SQLite

  nudge_engine.generate_nudges() → picks top 1-2 from candidates
  _send_notifications(user_id, nudges) → Web Push + Telegram
  state.record_nudges() → nudge_log

MIDDAY JOB (12:00):
  Synthetic insight with needs_activation=True → activation nudge

EVENING JOB (19:00):
  Same as morning but appends "evening_reflection" flag, strictness=0.4

PER-TASK NUDGES (every minute):
  Checks tasks WHERE nudge_enabled=1 AND status!='completed'
  Matches current HH:MM against nudge_times/nudge_time
  Matches current weekday against nudge_days
  Fires: custom nudge_message or "Reminder: {title} needs attention"

DASHBOARD POLLING:
  GET /api/context → every 60s
  GET /api/nudges → every 60s
  GET /api/insight → every 5 min
```

---

## 4. What the LLM Actually Sees

The LLM (Gemini) receives this context per call:

```python
{
    "goals": ["goal title 1", "goal title 2"],          # just titles, no descriptions
    "tasks": [
        {"id": "...", "title": "...", "status": "overdue", "due_date": "2026-04-10"},
    ],
    "recent_actions": ["acknowledged", "snoozed"],       # just action_type strings
    "behavior_patterns": [],                              # ALWAYS EMPTY
    "daily_summary": "User has 2 goal(s), 5 task(s) (1 overdue, 3 pending), and 3 recent action(s)."
}
```

**What's missing from the LLM context:**
- Contact information (never forwarded)
- Calendar events (never forwarded)
- Goal descriptions and priorities
- Task nudge configs and custom messages
- Historical patterns (table is empty)
- Previous insights (not fed back)
- Action metadata (only type, not what was acknowledged)
- Time/day context (what day of week, what time of day)

---

## 5. ChromaDB — Semantic Memory

ChromaDB is fully set up but **only used at ingest time**. The `semantic_search()` function exists and works, but nothing in the pipeline calls it. It could power:
- "What tasks are similar to X?"
- Natural language queries against user memory
- LLM retrieval-augmented generation (RAG)

Collections created per user: `{user_id}_goals`, `{user_id}_tasks`, `{user_id}_contacts`, `{user_id}_events`

---

## 6. Testing Infrastructure

| Test | Type | Status |
|------|------|--------|
| `tests/test_full_system.py` | API integration (27 tests) | **Working (WS5)** |
| `tests/test_api_full.py` | Older API tests | Exists |
| `Memory/tests/` | Unit tests | Exists |
| `Orchestrator/tests/` | Unit tests | Exists |
| `llm_module/tests/` | Unit tests | Exists |
| `Remind/test_nudge_engine.py` | Unit tests | Exists |
| `test_api.py` (root) | Legacy API test | Exists |
| `test_signals.py` (root) | Signal/pipeline tests | Exists |
