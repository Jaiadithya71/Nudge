# Phase 5: Deep Intelligence

> Prerequisite: Phases 2-4 (patterns, contacts, domains all feeding data)
> Goal: The LLM truly knows you — your history, your personality, your trajectory.
> When complete: Insights feel like they come from someone who's watched you for months.

---

## Current LLM Limitations

The LLM currently sees:
- Today's task titles and statuses
- Goal titles (no descriptions)
- Recent action types (no context)
- Empty behavior patterns array
- A one-line daily summary

It does NOT see:
- Yesterday's insight or what happened after it
- Your contact relationships
- Your calendar
- Your productivity patterns
- How you responded to previous nudges
- How long tasks have been pending
- Your personality or communication preferences

---

## Workstreams

### WS16: Enriched LLM Context

**Purpose:** Feed the LLM everything it needs to generate genuinely personal insights.

**What to change in `_context_to_llm_dict()`:**

```python
{
    "goals": [
        {"title": "Ship product", "priority": "high", "tasks_total": 5, "tasks_done": 2}
    ],
    "tasks": [
        {"title": "Renew insurance", "status": "overdue", "due_date": "2026-04-10",
         "days_overdue": 4, "times_snoozed": 3, "domain": "finance"}
    ],
    "today_events": [
        {"title": "1:1 with John", "time": "14:00-14:30",
         "attendee": "John Smith", "last_met_days_ago": 15}
    ],
    "behavior_patterns": [
        "Most productive 9am-11am on weekdays",
        "Ignores 85% of reflection nudges",
        "Tends to complete tasks in bursts on Tuesday and Thursday"
    ],
    "recent_actions": [
        "Acknowledged 'correction' nudge about overdue tasks (2 hours ago)",
        "Completed 'Review PR' (yesterday)",
        "Snoozed 'Call dentist' for the 7th time (yesterday)"
    ],
    "yesterday_insight": "User is falling behind on Finance tasks. 3 overdue.",
    "daily_summary": "Day 47 of usage. 2 goals, 8 tasks (3 overdue, 4 pending, 1 done today). Calendar has 3 events. No contact decay alerts."
}
```

---

### WS17: Semantic Memory (RAG)

**Purpose:** Use ChromaDB to recall relevant past context before generating insights.

**What to build:**

1. **Pre-insight retrieval:** Before calling Gemini, query ChromaDB with today's context as the search query
2. **Inject results into prompt:** "Relevant past context: [semantic search results]"
3. **Embed daily insights:** Store each day's insight summary in ChromaDB for future retrieval
4. **Embed action summaries:** Weekly summaries of user actions, embedded for semantic recall

**This uses `semantic_search()` which is already built and tested — just never called.**

---

### WS18: Insight Continuity

**Purpose:** The LLM remembers what it said yesterday and whether the user acted on it.

**What to build:**

1. **Rolling insight buffer:** Store last 7 days of insights in `orchestrator_state` (or a new table)
2. **Inject into prompt:** "Here are your insights from the last 3 days and what happened after each"
3. **Track insight follow-through:** Did the user act on yesterday's recommendation?
4. **Enables:** "I suggested tackling Finance tasks yesterday. You completed 1 of 3 — keep going."

---

### WS19: Personality Model

**Purpose:** A compact profile of who the user is, maintained automatically.

**What to build:**

1. **Profile document** (stored in ChromaDB or `orchestrator_state`):
   ```json
   {
       "communication_preference": "strict",
       "peak_hours": [9, 10, 11, 14, 15],
       "avoidance_domains": ["health"],
       "strength_domains": ["work"],
       "nudge_type_effectiveness": {
           "correction": 0.7,
           "activation": 0.3,
           "reflection": 0.1
       },
       "task_completion_style": "burst",
       "average_tasks_per_week": 12,
       "usage_days": 47,
       "last_updated": "2026-06-01"
   }
   ```

2. **Auto-update:** Recompute weekly from behavior_patterns
3. **Feed into LLM system prompt:** The LLM knows it's talking to someone who prefers strict nudges, works in bursts, and avoids health tasks

---

### WS20: Model Upgrade Path

**Purpose:** Prepare for switching to more capable LLMs as context grows.

**What to document/prepare:**

1. **Abstraction:** `llm_module/llm_client.py` already isolates the API call. Document the interface.
2. **Context budget:** Calculate token usage at each phase. Current: ~500 tokens. Phase 5: ~3000 tokens.
3. **Options:**
   - Gemini 2.5 Pro (more capable, still free tier with limits)
   - Claude API (better reasoning, paid)
   - Local Llama 3 via Ollama (free, private, unlimited — but lower quality)
4. **Multi-model strategy:** Use cheap model for daily insights, expensive model for weekly deep analysis

---

## Phase 5 Success Criteria

1. LLM context includes: goal progress, task age, snooze counts, events, contacts, patterns, yesterday's insight
2. `semantic_search()` is called before insight generation to inject relevant history
3. Insights reference yesterday's recommendations and track follow-through
4. Personality model exists and is fed into every LLM call
5. A user at Day 60 gets qualitatively different (better, more personal) insights than Day 1
6. System works with at least 2 different LLM backends (Gemini + one other)
