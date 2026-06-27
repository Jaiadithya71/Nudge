# Phase 2: The System Learns Your Patterns

> Prerequisite: Phase 1 complete ✅
> Goal: Analyze user behavior, detect patterns, adapt nudges, add recurring tasks.
> When complete: The system gets smarter the more you use it.
> **LLM dependency: NONE. This entire phase is SQL queries + Python logic.**

---

## Why This Phase Matters

Right now the system treats Day 1 and Day 100 identically. It has no memory of:
- Which nudges you respond to vs. ignore
- What time of day you're most productive
- Which tasks you chronically avoid
- Whether its nudges actually help or just annoy you

All the raw data to answer these questions **already exists** in `user_actions` and `nudge_log`. It's just never analyzed.

---

## LLM Usage: Zero Additional Calls

| Component | Uses LLM? | What It Uses Instead |
|-----------|-----------|---------------------|
| Pattern detection (WS6) | **No** | SQL `GROUP BY` + `COUNT` aggregations over user_actions and nudge_log |
| Pattern-informed nudges (WS7) | **No** | Python `if/else` rules reading behavior_patterns rows |
| Recurring tasks (WS8) | **No** | `datetime` arithmetic for next occurrence date |
| Effectiveness dashboard (WS9) | **No** | SQL queries rendered as numbers and percentages |

The existing daily LLM call remains unchanged. The only improvement: `behavior_patterns` (currently empty) gets populated by SQL, so the single daily LLM call receives richer context — making it more useful without costing more.

---

## Workstream Breakdown

### WS6: Action Analysis Engine

> **LLM calls: 0.** Pure SQL aggregation + Python math.

**Purpose:** Read the `user_actions` and `nudge_log` tables, compute behavioral patterns, write to `behavior_patterns`.

**Scope:** New file + scheduler addition

**What to build:**

Create `Memory/pattern_detector.py`:

```python
def detect_patterns(user_id: str) -> list[dict]:
    """
    Analyze user_actions and nudge_log to detect behavioral patterns.
    Returns a list of pattern dicts to upsert into behavior_patterns table.
    
    No LLM involved — all detection is SQL GROUP BY + Python arithmetic.
    """
```

Patterns to detect (start with these 6):

| Pattern Type | How to Detect | Example Output |
|---|---|---|
| `nudge_response_rate` | Count acknowledged vs. total in nudge_log joined with user_actions | "User acknowledges 60% of correction nudges, ignores 90% of reflection nudges" |
| `productive_hours` | Group task completions (action_type='completed') by hour-of-day | "User completes most tasks between 9am-11am and 2pm-4pm" |
| `avoidance_target` | Tasks that have been snoozed 3+ times | "User has snoozed 'Call dentist' 7 times in 14 days" |
| `completion_trend` | Compare task completions this week vs. last week | "Task completion rate is declining: 8 last week → 3 this week" |
| `day_of_week_pattern` | Group completions by weekday | "User is most productive on Tuesdays and Thursdays" |
| `inactivity_windows` | Gaps between actions longer than 4 hours | "User is typically inactive 12pm-2pm (lunch) and after 8pm" |

**Data sources (all SQL — no LLM):**

```sql
-- Nudge response rate
SELECT nl.type, ua.action_type, COUNT(*)
FROM nudge_log nl
LEFT JOIN user_actions ua ON ua.entity_id = nl.id
WHERE nl.sent_at > datetime('now', '-30 days')
GROUP BY nl.type, ua.action_type;

-- Task completions by hour
SELECT strftime('%H', ua.created_at) as hour, COUNT(*)
FROM user_actions ua
WHERE ua.action_type IN ('completed', 'acknowledged')
AND ua.created_at > datetime('now', '-30 days')
GROUP BY hour;

-- Avoidance targets (snoozed 3+ times)
SELECT ua.entity_id, COUNT(*) as snooze_count, 
       (SELECT title FROM tasks WHERE id = ua.entity_id) as task_title
FROM user_actions ua
WHERE ua.action_type = 'snoozed'
GROUP BY ua.entity_id
HAVING snooze_count >= 3;
```

**Schema for pattern output:**
```python
{
    "id": "uuid",
    "pattern_type": "nudge_response_rate",     # one of the 6 types above
    "description": "User acknowledges 60% of correction nudges, ignores 90% of reflection nudges",
    "confidence": 0.85,                         # 0.0-1.0 based on sample size
    "last_updated": "2026-04-14T12:00:00Z"
}
```

**When to run:** Nightly at 23:00 (add to orchestrator as a `pattern_detection` job type). Simpler and cheaper than event-driven.

**Files to create/modify:**

| File | Change |
|------|--------|
| `Memory/pattern_detector.py` | NEW — all detection logic (pure SQL + Python) |
| `Memory/memory.py` | Add `upsert_pattern(user_id, pattern)` and `get_patterns(user_id)` |
| `Orchestrator/orchestrator.py` | Add `_run_pattern_job()`, wire into scheduler (run at 23:00) |

**Acceptance criteria:**
1. After 5+ days of real usage, `behavior_patterns` table has 3+ rows
2. `GET /api/context` returns populated `behavior_patterns` array
3. Patterns update nightly without manual intervention
4. Pattern confidence increases with more data (>50 actions = high confidence)

---

### WS7: Pattern-Informed Nudges

> **LLM calls: 0.** Python if/else rules reading pattern data from SQLite.

**Purpose:** Use detected patterns to make nudge decisions smarter.

**Depends on:** WS6

**What to change:**

1. **Patterns flow to LLM automatically (no code change needed)**

   `_context_to_llm_dict()` already converts `behavior_patterns` to description strings. Once WS6 populates the table, the daily LLM call will see them. No new LLM calls.

2. **Adapt nudge engine rules (pure Python logic)**

   `Remind/nudge_engine.py` — Add pattern-aware logic to `_build_candidates()`:
   
   ```python
   # If user ignores 80%+ of a nudge type, stop generating it
   # If user has an avoidance target, escalate its priority
   # If user is outside productive hours (from pattern), delay nudge timing
   ```

   These are `if` statements checking pattern data, not LLM calls.

3. **Adjust strictness dynamically (Python arithmetic)**

   Instead of a global strictness setting, modulate per-nudge:
   - Chronically snoozed task → increase strictness for that task's nudge
   - Task the user usually handles quickly → decrease strictness

**Files to modify:**

| File | Change |
|------|--------|
| `Remind/nudge_engine.py` | Add `_apply_pattern_adjustments()` to modify candidates based on patterns |
| `Orchestrator/orchestrator.py` | Pass patterns to nudge engine (already in context, just needs reading) |

**Acceptance criteria:**
1. If a user ignores 80%+ of reflection nudges over 2 weeks, the system stops generating them
2. Chronically snoozed tasks get escalated nudge priority
3. Nudge messages reference the user's patterns: "You've been putting this off for 2 weeks"

---

### WS8: Recurring Tasks

> **LLM calls: 0.** Date arithmetic using Python's `datetime` module.

**Purpose:** Tasks that auto-recreate on a schedule.

**What to build:**

1. **Schema addition:**
   ```sql
   ALTER TABLE tasks ADD COLUMN recurrence TEXT;
   -- null = one-time task
   -- 'daily'
   -- 'weekly:mon,wed,fri'
   -- 'monthly:15'
   -- 'yearly:04-14'
   ```

2. **Recurrence engine:** `Memory/recurrence.py`
   ```python
   def process_completed_recurring_tasks(user_id: str) -> list[dict]:
       """
       Find completed tasks with recurrence set.
       Create next occurrence with status='pending' and appropriate due_date.
       Returns list of newly created tasks.
       
       No LLM — just datetime arithmetic:
         'weekly:sun' + completed today → next Sunday's date
         'monthly:15' + completed today → 15th of next month
       """
   ```

3. **Wire into orchestrator:** Call `process_completed_recurring_tasks()` at the end of the morning job.

4. **Dashboard UI:** Add recurrence selector to TaskRow editor (between due date and nudge times):
   - "One time" (default)
   - "Daily"
   - "Weekly on..." (day picker)
   - "Monthly on the..."
   - "Yearly on..."

5. **API:** `PATCH /api/tasks/{id}` already accepts arbitrary fields — just add `recurrence` to the allowed set in `Memory/memory.py` `update_task()`.

**Files to create/modify:**

| File | Change |
|------|--------|
| `Memory/schema.sql` | Add `recurrence` column to tasks |
| `Memory/recurrence.py` | NEW — recurrence processing logic (datetime math only) |
| `Memory/memory.py` | Add `recurrence` to allowed update fields, add migration for existing DBs |
| `Orchestrator/orchestrator.py` | Call recurrence processing in morning job |
| `api/routes/tasks.py` | Add `recurrence` to CreateTaskRequest and UpdateTaskRequest |
| `Dashboard/components/TaskList.tsx` | Add recurrence selector UI |
| `Dashboard/lib/api.ts` | Add `recurrence` to createTask/updateTask payloads |
| `Dashboard/types/index.ts` | Add `recurrence: string \| null` to Task type |

**Acceptance criteria:**
1. Create task "Buy groceries" with recurrence "weekly:sun"
2. Complete it → new "Buy groceries" task auto-created with next Sunday's due date
3. Dashboard shows recurrence badge on task: "Every Sun"
4. Nudge fires on Sunday at configured time for the new occurrence
5. Deleting a recurring task does NOT create the next occurrence

---

### WS9: Effectiveness Dashboard

> **LLM calls: 0.** SQL COUNT/GROUP BY queries rendered as numbers and percentages.

**Purpose:** Show the user how the system is performing — are nudges actually helping?

**What to build:**

1. **New dashboard section accessible from header button: "Stats"**

   Show (all from existing SQLite data — no LLM):
   - Tasks completed this week vs. last week (SQL COUNT with date filters)
   - Nudge response rate: % acknowledged vs. snoozed vs. ignored (SQL GROUP BY action_type)
   - Most snoozed tasks (SQL GROUP BY entity_id HAVING count >= 3)
   - Productive hours (SQL GROUP BY strftime('%H', created_at))
   - Current behavior patterns (direct read from behavior_patterns table)

2. **API endpoint:** `GET /api/stats`
   ```python
   {
       "period": "last_30_days",
       "tasks_completed": 23,
       "tasks_created": 31,
       "completion_rate": 0.74,
       "nudge_response_rate": {
           "acknowledged": 0.45,
           "snoozed": 0.35,
           "ignored": 0.20
       },
       "most_snoozed": [
           {"task_id": "...", "title": "Call dentist", "snooze_count": 7}
       ],
       "productive_hours": [9, 10, 11, 14, 15],
       "patterns": [...]
   }
   ```

3. **Dashboard component:** `Dashboard/components/StatsPanel.tsx`
   - Accessible from a "Stats" button in the header (same pattern as Settings)
   - Simple numbers and percentage bars using CSS widths — no charts library
   - Matches existing minimal black-and-white design

**Files to create/modify:**

| File | Change |
|------|--------|
| `api/routes/stats.py` | NEW — stats endpoint (SQL queries, no LLM) |
| `api/services/stats_service.py` | NEW — queries against user_actions and nudge_log |
| `api/main.py` | Register stats router |
| `Dashboard/components/StatsPanel.tsx` | NEW — stats display |
| `Dashboard/app/page.tsx` | Add stats button to header, toggle panel |
| `Dashboard/lib/api.ts` | Add `getStats()` function |

**Acceptance criteria:**
1. After 1 week of use, `/api/stats` returns meaningful numbers
2. Dashboard shows completion trend, response rate, and avoidance targets
3. Data refreshes on page load (no polling needed — stats are not time-sensitive)

---

## Execution Order

```
Phase 2A (sequential — each builds on the previous):
  WS6: Action Analysis Engine     ← foundation, must be first
  WS7: Pattern-Informed Nudges    ← uses WS6 output

Phase 2B (parallel — independent of 2A):
  WS8: Recurring Tasks            ← schema + UI, no pattern dependency
  WS9: Effectiveness Dashboard    ← reads existing data, no pattern dependency

Recommended order:
  1. WS8 (Recurring Tasks) — most user-visible value, simplest
  2. WS6 (Action Analysis) — enables everything else
  3. WS9 (Stats Dashboard) — can show data even before patterns exist
  4. WS7 (Pattern-Informed Nudges) — the payoff, requires WS6 data
```

---

## Phase 2 Success Criteria

After Phase 2 is complete, the system should:

1. Auto-recreate recurring tasks when completed
2. Detect and display at least 3 behavioral patterns from usage history
3. Adapt nudge behavior based on detected patterns (suppress ignored types, escalate avoided tasks)
4. Show the user a stats page with their completion rate, response rate, and productivity hours
5. The LLM context includes real behavior patterns (not empty arrays) — at no extra API cost
6. A user who has used the system for 2 weeks sees noticeably different nudges than a new user
7. **Total additional LLM calls introduced: 0**
