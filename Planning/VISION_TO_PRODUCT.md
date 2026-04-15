# Nudge — From Vision to Product

> How the original vision maps to concrete phases, and what each phase unlocks.
> This document is the north star. Everything else is implementation detail.

---

## The Vision (from Initial_Vision.md)

A digital duplicate of a physical persona that:
1. Knows your day-to-day activities, habits, plans, and future goals
2. Knows your buying activities and daily chores
3. Has an extensive collection of all people you know and your relationships
4. Handles most normal actions a user performs on a periodic basis
5. Is extensible so other developers can attach new modules
6. User data is exportable/migratable
7. Can substitute for the user when asked

---

## The Reality Check

This vision describes a 5-year product. The mistake in previous iterations was trying to build it all at once. The correct approach:

**Each phase must deliver something you use daily. If you stop at any phase, you still have a useful tool.**

---

## Phase Map

```
Phase 1 ✅  — Reliable reminder tool (COMPLETE)
Phase 2     — The system learns your patterns
Phase 3     — The system knows your people
Phase 4     — Recurring life management
Phase 5     — Deep intelligence (the LLM actually knows you)
Phase 6     — The system acts (not just reminds)
Phase 7     — Extensibility and data ownership
```

Each phase builds on the previous. Skipping phases creates the same failure mode as before — a complex system that doesn't work reliably.

---

## Phase 1: Reliable Reminder Tool ✅ COMPLETE

**What it delivers:** A task manager with push notifications that actually reach your phone, with AI-generated nudges that reference your real tasks.

**What was built (5 workstreams, April 2026):**
- Task and goal CRUD on the dashboard
- Per-task nudge scheduling (times, days, custom messages)
- Web Push + Telegram unified delivery
- Task-aware nudge messages ("Renew insurance is 3 days overdue")
- Service worker notification actions logged to backend
- Full API test suite

**What it proves:** The system can reliably observe (tasks), decide (nudge engine), and act (notifications). The Observe → Act pipeline works.

---

## Phase 2: The System Learns Your Patterns

**What it delivers:** The system notices your behavior — when you're productive, what you avoid, what you ignore — and adapts.

**Vision mapping:** "Knows your day-to-day activities" + "Knows your habits"

**Why it matters:** Right now the system treats every day the same. It doesn't know you're more productive on Tuesdays, or that you always ignore evening nudges, or that you snooze "Call dentist" every time. Without patterns, nudges are guesses. With patterns, nudges become personal.

### What needs to happen:

**2A. Action Analysis Engine**
- Read `user_actions` table (currently write-only, never analyzed)
- Compute patterns: response rates by nudge type, time-of-day productivity, task completion trends, recurring snooze targets
- Write findings to `behavior_patterns` table (currently empty)
- Run as a scheduled job: nightly or weekly

**2B. Pattern-Informed Nudges**
- Feed `behavior_patterns` into the LLM context (already carried in UserContext, just empty)
- Feed patterns into nudge engine rules: if user always ignores activation nudges, stop sending them; if user completes more tasks at 3pm, shift nudge timing
- Adjust strictness per-pattern: escalate for chronically snoozed tasks, soften for tasks the user handles quickly

**2C. Recurring Tasks**
- Add `recurrence` column to tasks table: `daily`, `weekly:mon,wed,fri`, `monthly:15`, `custom:cron`
- When a recurring task is completed, auto-create the next occurrence
- Dashboard UI: recurrence selector in task editor
- Nudge engine treats recurring tasks that haven't been done today as "due"

**2D. Feedback Loop Dashboard**
- Show the user their own patterns: "You complete 80% of tasks on Mondays, 30% on Fridays"
- Show nudge effectiveness: "You acknowledge 60% of correction nudges, ignore 90% of reflection nudges"
- This data already exists in `nudge_log` and `user_actions` — just needs a UI

### Infrastructure already in place:
- `behavior_patterns` table with schema
- `user_actions` table with all interactions logged
- `nudge_log` with every nudge ever sent
- `GET /api/evaluation/today` as a starting point
- `behavior_patterns` already carried in UserContext to LLM

### Key schema addition:
```sql
ALTER TABLE tasks ADD COLUMN recurrence TEXT;  -- null = one-time
-- Values: 'daily', 'weekly:mon,wed,fri', 'monthly:15', 'yearly:04-14'
```

---

## Phase 3: The System Knows Your People

**What it delivers:** Relationship awareness — who matters to you, when you last connected, who to reach out to.

**Vision mapping:** "Extensive collection of all people the user knows"

**Why it matters:** You already sync Google Contacts into SQLite. But the data sits there unused — no UI, no nudges, no analysis. Contacts exist in `UserContext` but the LLM never sees them (dropped in `_context_to_llm_dict()`).

### What needs to happen:

**3A. Contact Dashboard**
- Show contacts on the dashboard: name, email, last interaction, importance score
- Manual importance tagging (1-5 stars or high/medium/low)
- "Last contacted" derived from calendar events + manual logs

**3B. Relationship Decay Detection**
- Nightly job: scan contacts where `last_interaction` is older than a threshold
- Threshold based on importance: high = 14 days, medium = 30 days, low = 90 days
- Generate "reach out" nudges: "You haven't talked to Mom in 3 weeks"

**3C. Meeting Prep Context**
- When a Google Calendar event includes attendees, match against contacts
- Feed contact context into the LLM: "Meeting with John at 2pm — you last met on March 5"
- Dashboard shows contact cards for today's meeting attendees

**3D. Forward Events to LLM**
- Currently `_context_to_llm_dict()` drops events entirely
- Add today's events to the LLM context: event titles, times, attendees
- Enables insights like: "You have 4 meetings today — protect focus time for 'Write report'"

### Infrastructure already in place:
- `contacts` table populated by Google Contacts sync
- `events` table populated by Google Calendar sync
- Contact data already in UserContext (just not forwarded to LLM or shown in UI)
- ChromaDB embeddings for contacts already created on ingest

---

## Phase 4: Recurring Life Management

**What it delivers:** The system manages your periodic obligations — renewals, bills, groceries, appointments — without you needing to remember them.

**Vision mapping:** "Buying activities and daily chores" + "Handles most normal actions a user performs on a periodic basis"

**Why it matters:** This is where the system transitions from "I remind you about things you entered" to "I know your life has recurring needs and I track them for you."

### What needs to happen:

**4A. Life Domains**
- Categories for recurring obligations: Health, Finance, Home, Social, Work
- Each domain has its own expected cadence: dentist (6 months), insurance renewal (yearly), groceries (weekly)
- Dashboard section: "Life" or "Routines"

**4B. Smart Recurrence from History**
- Detect patterns from completed recurring tasks: "User buys groceries every Sunday"
- Suggest recurrence rules for tasks that look periodic
- Auto-create if the user approves

**4C. Anticipatory Nudges**
- Instead of reminding when overdue, remind before due: "Insurance renewal is in 2 weeks — start the paperwork"
- Lead time based on task complexity (learned from how long the user typically takes)

**4D. Calendar-Aware Scheduling**
- When creating a reminder, check the user's calendar for free slots
- Suggest: "You have a free hour at 2pm tomorrow — good time for 'Call dentist'?"
- Requires Phase 3's calendar context forwarding

### Infrastructure needed:
- Task categories/domains (new column or separate table)
- Recurrence engine (from Phase 2C)
- Anticipatory nudge type (new nudge type: `anticipatory`, fires X days before due)

---

## Phase 5: Deep Intelligence

**What it delivers:** The LLM actually understands you — your patterns, your personality, your history — and gives genuinely useful insights.

**Vision mapping:** "A digital duplicate" + core intelligence layer

**Why it matters:** Currently the LLM sees a flat snapshot of today. It has no memory of yesterday, last week, or last month. It can't say "You've been avoiding this task for 2 weeks" because it doesn't know what happened 2 weeks ago.

### What needs to happen:

**5A. Enrich LLM Context**
- Include in the prompt:
  - Behavior patterns (from Phase 2): "User is most productive 9-11am", "User ignores reflection nudges"
  - Contact context (from Phase 3): relationships, last interaction
  - Calendar events (from Phase 3D): today's schedule
  - Historical insights: what the LLM said yesterday, and whether the user acted on it
  - Goal progress: % of tasks completed per goal, trend direction
  - Task age: how long each task has been pending

**5B. Semantic Memory for RAG**
- Use ChromaDB's `semantic_search()` (already built, never called)
- Before generating insight, search for relevant past actions, patterns, and notes
- Feed top results into the LLM prompt as context
- Enables: "The last time you had a week like this, you completed 3 tasks on Thursday — try that again"

**5C. Multi-Turn Insight Memory**
- Store each day's insight in a rolling buffer (last 30 days)
- Feed recent insights back into the prompt
- Enables continuity: "Yesterday I noted you were falling behind on X — you haven't addressed it"

**5D. Personality Model**
- Over time, build a compact personality profile from patterns:
  - Communication style preference (strict vs. supportive)
  - Peak productivity hours
  - Avoidance triggers (what gets snoozed most)
  - Goal commitment level (how often goals are abandoned vs. completed)
- Store as a structured document in ChromaDB
- Feed into every LLM call as system context

**5E. Switch to More Capable LLM (When Needed)**
- Current: Gemini 2.5 Flash (free tier, 1 call/day)
- As context gets richer, may need: longer context window, better reasoning
- Options: Gemini 2.5 Pro, Claude API, local Llama model
- Architecture already supports swapping: just change `llm_client.py`

### Infrastructure already in place:
- ChromaDB with `semantic_search()` — fully built, never called
- `behavior_patterns` table in UserContext — empty but wired
- `insight_cache` in orchestrator_state — could store history
- Retry + fallback logic in llm_module

---

## Phase 6: The System Acts

**What it delivers:** Beyond reminding — the system can take actions on your behalf when authorized.

**Vision mapping:** "Be a substitute to him/her when asked" + "Handles most normal actions"

**Why it matters:** This is the leap from assistant to agent. Extremely powerful, but requires high trust built from Phases 1-5.

### What might this look like:
- Send a "thinking of you" message to a contact you haven't reached out to
- Auto-schedule a task into a free calendar slot
- Draft an email response based on context
- Reorder groceries from a saved list
- File an expense report from receipts

### Prerequisites:
- High reliability from Phases 1-5 (user must trust the system)
- Action authorization framework (user approves action templates, system executes)
- Undo/confirmation for irreversible actions
- Audit log of all automated actions

### This phase is speculative — design it when Phases 1-5 are proven.

---

## Phase 7: Extensibility and Data Ownership

**What it delivers:** Other developers can build modules. Users own and can export their data.

**Vision mapping:** "Extensible so other developers can create and attach new modules" + "User data should be exportable"

### What needs to happen:

**7A. Plugin Architecture**
- Define a module interface: `register()`, `ingest()`, `get_context()`, `get_nudge_candidates()`
- Plugin discovery: drop a Python file in `plugins/`, auto-loaded on startup
- Each plugin gets its own SQLite table namespace and ChromaDB collection

**7B. Data Export**
- `GET /api/export` — returns a ZIP of:
  - SQLite database (complete)
  - ChromaDB vectors (serialized)
  - Settings and preferences
- JSON export option for portability to other systems

**7C. Data Import**
- Accept exported ZIP and hydrate a new user's database
- Enables: migration between devices, backup/restore

### Prerequisites:
- Stable module interface (finalized after Phase 5)
- This phase is about scaling the system to others — do it last

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-10 | Archived Notion connectors | Notion CRUD was unreliable and added complexity without value. SQLite is the source of truth. |
| 2026-04-12 | Dashboard is the control center, not Notion | System must be self-contained. External dependencies reduce reliability. |
| 2026-04-14 | Phase 1 complete (5 workstreams) | Unified notifications, task-aware nudges, goal UI, SW actions, full test suite. |
| 2026-04-14 | Phase 2 is next priority | Learning from behavior is the foundation for all intelligence features. Without it, the system can never get smarter. |

---

## Invariants (True Across All Phases)

1. **Single user first.** Multi-user is an architecture property, not a product requirement.
2. **SQLite is the source of truth.** All external systems sync into it.
3. **LLM is called sparingly.** Free tier constraint. Cache aggressively. 1 call/day max for now.
4. **Mock mode must always work.** Every feature must be testable without API keys.
5. **The system must be useful without AI.** If Gemini is down, tasks and reminders still work.
6. **Per-user data isolation.** Separate databases, separate vector stores.
7. **No silent failures.** Log everything. Fallback gracefully. Never crash the pipeline.
