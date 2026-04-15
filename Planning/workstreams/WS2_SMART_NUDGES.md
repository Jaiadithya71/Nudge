# WS2: Task-Aware Nudge Messages

> Priority: P0 — Critical
> Dependencies: None
> Estimated scope: 1 file changed

---

## Problem

Nudge messages are generic templates like:
- "You have overdue tasks demanding your attention."
- "You haven't made progress today."

They don't mention which tasks, how many, or what's actually overdue. This makes them easy to ignore — they feel like spam, not a personal nudge.

The `_get_task_nudge_message()` function in `Remind/nudge_engine.py` already checks for user-written `nudge_message` on overdue tasks, but:
1. It only returns the FIRST one, ignoring all others
2. If no user-written message exists, it falls back to a generic template
3. The templates never reference task names, counts, or due dates

---

## What To Do

### Change 1: Make `_build_candidates()` produce task-aware messages

**File:** `Remind/nudge_engine.py`

Replace the `_get_task_nudge_message()` function (line 145) with a more capable version:

```python
def _get_task_context(user_context: dict) -> dict:
    """
    Extract task-level details for message generation.
    Returns: {
        overdue_titles: list[str],
        overdue_count: int,
        pending_count: int,
        custom_messages: list[str],   # user-written nudge_message values
        oldest_overdue_title: str | None,
        oldest_overdue_days: int | None,
    }
    """
    tasks = user_context.get("tasks", [])
    overdue = []
    pending_count = 0
    custom_messages = []

    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = task.get("status", "")
        if status == "overdue":
            overdue.append(task)
            if task.get("nudge_message"):
                custom_messages.append(task["nudge_message"])
        elif status == "pending":
            pending_count += 1

    overdue_titles = [t.get("title", "Untitled") for t in overdue]

    # Find the oldest overdue task by due_date
    oldest_title = None
    oldest_days = None
    for t in overdue:
        dd = t.get("due_date")
        if dd:
            try:
                from datetime import datetime
                due = datetime.fromisoformat(str(dd).replace("Z", "+00:00"))
                days = (datetime.now(due.tzinfo if due.tzinfo else None) - due).days
                if oldest_days is None or days > oldest_days:
                    oldest_days = days
                    oldest_title = t.get("title", "Untitled")
            except (ValueError, TypeError):
                pass

    return {
        "overdue_titles": overdue_titles,
        "overdue_count": len(overdue),
        "pending_count": pending_count,
        "custom_messages": custom_messages,
        "oldest_overdue_title": oldest_title,
        "oldest_overdue_days": oldest_days,
    }
```

### Change 2: Add task-aware message templates

**File:** `Remind/nudge_engine.py`

Add a new function below `_pick_message()`:

```python
def _pick_task_aware_message(nudge_type: str, task_ctx: dict, strictness: float = 0.7) -> str:
    """
    Generate a message that references actual task names and counts.
    Falls back to generic templates if no task context is available.
    """
    # If user wrote custom messages for overdue tasks, prefer those
    if nudge_type == "correction" and task_ctx["custom_messages"]:
        return task_ctx["custom_messages"][0]

    overdue = task_ctx["overdue_titles"]
    oldest = task_ctx["oldest_overdue_title"]
    oldest_days = task_ctx["oldest_overdue_days"]

    if nudge_type == "correction" and overdue:
        if len(overdue) == 1:
            base = f'"{overdue[0]}" is overdue.'
        elif len(overdue) == 2:
            base = f'"{overdue[0]}" and "{overdue[1]}" are both overdue.'
        else:
            base = f'"{overdue[0]}" and {len(overdue) - 1} other task(s) are overdue.'

        if oldest and oldest_days and oldest_days > 1:
            base += f" ({oldest} is {oldest_days} days late.)"

        if random.random() < strictness:
            return base + " Handle them now — not later."
        return base + " Pick one and take a small step."

    if nudge_type == "activation":
        pending = task_ctx["pending_count"]
        if pending > 0:
            if random.random() < strictness:
                return f"You have {pending} pending task(s) and no progress today. Start with one."
            return f"{pending} task(s) waiting. What's one small thing you can do right now?"

    # Fall back to generic templates for types without task context
    return _pick_message(nudge_type, strictness)
```

### Change 3: Wire it into `_build_candidates()`

**File:** `Remind/nudge_engine.py`

In the `_build_candidates()` function, replace the message generation logic. Currently (approx line 196-208):

```python
    # Use a user-written nudge message for correction nudges if available
    task_message = _get_task_nudge_message(user_context)

    for nudge_type, priority in triggers:
        if nudge_type in seen_types:
            continue
        seen_types.add(nudge_type)

        # Prefer the user's own message for correction nudges
        if nudge_type == "correction" and task_message:
            message = task_message
        else:
            message = _pick_message(nudge_type, strictness)
```

**Replace with:**

```python
    task_ctx = _get_task_context(user_context)

    for nudge_type, priority in triggers:
        if nudge_type in seen_types:
            continue
        seen_types.add(nudge_type)

        message = _pick_task_aware_message(nudge_type, task_ctx, strictness)
```

### Change 4: Update `_build_nudge_bank()` in orchestrator

**File:** `Orchestrator/orchestrator.py`

In `_build_nudge_bank()` (line 277), the bank generation also uses `_pick_message` and `_get_task_nudge_message`. Update it to use the new `_pick_task_aware_message`:

```python
def _build_nudge_bank(insight: dict, strictness: float, context=None) -> list[dict]:
    import nudge_engine as ne

    type_map = [
        ("correction",  "high"),
        ("strategic",   "medium"),
        ("activation",  "low"),
        ("reflection",  "low"),
        ("reminder",    "medium"),
    ]

    # Build task context for task-aware messages
    task_ctx = None
    if context is not None:
        ctx_data = context.model_dump() if hasattr(context, "model_dump") else context
        task_ctx = ne._get_task_context(ctx_data)

    bank = []
    for nudge_type, priority in type_map:
        if task_ctx:
            message = ne._pick_task_aware_message(nudge_type, task_ctx, strictness)
        else:
            message = ne._pick_message(nudge_type, strictness)
        bank.append({
            "type":     nudge_type,
            "message":  message,
            "priority": priority,
        })

    return bank
```

### Change 5: Remove the old `_get_task_nudge_message` function

After the above changes, `_get_task_nudge_message()` is unused. Delete it from `Remind/nudge_engine.py`.

---

## What NOT To Do

- Do NOT change the nudge types (correction, strategic, activation, reflection, reminder)
- Do NOT change the priority system (high, medium, low)
- Do NOT change the `generate_nudges()` public API signature
- Do NOT modify the rate limiting or dedup logic
- Do NOT add new nudge types

---

## Files Touched

| File | Change |
|------|--------|
| `Remind/nudge_engine.py` | Replace `_get_task_nudge_message` with `_get_task_context` + `_pick_task_aware_message`, update `_build_candidates()` |
| `Orchestrator/orchestrator.py` | Update `_build_nudge_bank()` to use new functions |

---

## Acceptance Criteria

1. Run `python main.py` — nudge messages should now contain actual task titles
2. Create a task "Renew insurance" with status overdue → correction nudge should say: `"Renew insurance" is overdue. Handle them now — not later.`
3. If a task has `nudge_message` set to "Stop avoiding this", that exact message should appear for correction nudges
4. If 3 tasks are overdue, message should say: `"Task A" and 2 other task(s) are overdue.`
5. Activation nudges should reference pending task count: `You have 4 pending task(s) and no progress today.`
6. Run existing tests: `python -m pytest Remind/test_nudge_engine.py` — fix any broken tests due to the interface change
7. Generic templates should still work for types without task context (strategic, reflection, reminder without overdue)
