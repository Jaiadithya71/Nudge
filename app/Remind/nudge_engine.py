"""
NUDGE ENGINE — nudge_engine.py
================================
Contract:  generate_nudges(insight, user_context, history, preferences) -> list
Spec:      Insight + UserContext -> Decision Engine -> Priority -> Type -> Message -> Output
Guide:     IMPLEMENTATION_GUIDE.md

Pipeline (per SPEC.md §4):
  Insight + Context
        ↓
  Decision Engine          (Step 1 — rule-based flag evaluation)
        ↓
  Priority Assignment      (Step 2 — HIGH / MEDIUM / LOW)
        ↓
  Nudge Type Selection     (Step 3 — correction / reminder / reflection / activation / productivity)
        ↓
  Message Generation       (Step 4 — templates, tone enforced by strictness)
        ↓
  Nudge Output             (list, max 2 per call, deduped against history)

Guarantees (per CONTRACT.md):
  - max 2 nudges per call
  - no duplicate nudge types (vs recent_nudges in history)
  - respect max_nudges_per_day limit
"""

from __future__ import annotations

import random
from datetime import datetime, time
from typing import Optional


# Legacy triggers removed in favor of boolean decision signals from LLM

PRIORITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# Message Templates  (IMPLEMENTATION_GUIDE.md — Step 4 + Step 5)
# Every pool has "strict" (call-out behavior) + "supportive" (offer action).
# Ratio is controlled by preferences["strictness"] (default 0.7).
# ---------------------------------------------------------------------------

_MESSAGES: dict[str, dict[str, list[str]]] = {
    "correction": {
        "strict": [
            "You've delayed this multiple times. Let's break it into something small and finish it today.",
            "You have overdue tasks demanding your attention. Tackle them now — not later.",
            "Your current trajectory puts your goal at risk. Course-correct immediately.",
            "You're falling behind on your commitments. Stop delaying and act now.",
        ],
        "supportive": [
            "It's okay to stumble — what matters is getting back on track. You can do this.",
            "Small steps count. Take just one action on your overdue tasks right now.",
        ],
    },
    "productivity": {
        "strict": [
            "You're completing fewer tasks than usual. Focus on 1 high-impact task now.",
            "Your completion rate is declining. Pick one task and finish it before anything else.",
            "Productivity drop detected. Identify the block and clear it today.",
            "Fewer tasks done than expected. Stop planning and start executing.",
        ],
        "supportive": [
            "You've done it before — pick one task and make a dent.",
            "A focused 25-minute block can turn things around. Try it now.",
        ],
    },
    "reminder": {
        "strict": [
            "Repeated delays compound. This task has been pushed back too many times.",
            "You've postponed this before. Don't let a pattern of delay define your progress.",
            "Each reminder ignored adds more weight later. Handle it now.",
            "Delay is a decision. Choose differently this time.",
        ],
        "supportive": [
            "A gentle nudge: this task is still waiting. A few minutes is all it takes.",
            "You're capable of more than you give yourself credit for. Tackle this one.",
        ],
    },
    "activation": {
        "strict": [
            "You haven't made progress today. Start with one small task to build momentum.",
            "Extended inactivity is drift, not rest. Re-engage with your goals now.",
            "You've been inactive. Choose a task and start — the first step is the hardest.",
            "No activity logged. Inactivity is a choice. Make a different one.",
        ],
        "supportive": [
            "It's been quiet lately. Reconnect with what matters to you.",
            "What's one small thing you can do toward your goal right now?",
        ],
    },
    "reflection": {
        "strict": [
            "Take a moment to assess: are your daily actions aligned with your goals?",
            "Patterns of delay deserve honest reflection. What's holding you back?",
        ],
        "supportive": [
            "Reflection time: what worked today, and what can shift tomorrow?",
            "Progress is built one honest look at a time. What do you notice?",
        ],
    },
    "strategic": {
        "strict": [
            "Your long-term goals are at risk due to your daily execution. Re-evaluate your approach.",
            "You are working hard but off-target. Align your immediate tasks with your overarching goals.",
        ],
        "supportive": [
            "Take a step back. What is the most strategic move you can make today to secure your goals?",
            "Let's refocus. Make sure today's tasks directly drive your big goals forward.",
        ],
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pick_message(nudge_type: str, strictness: float = 0.7) -> str:
    """Return a message biased by strictness (0.0 = all supportive, 1.0 = all strict)."""
    pool = _MESSAGES.get(nudge_type, _MESSAGES["reminder"])
    if random.random() < strictness:
        return random.choice(pool["strict"])
    return random.choice(pool["supportive"])


def _pick_task_aware_message(nudge_type: str, task_ctx: dict, strictness: float = 0.7) -> str:
    """
    Generate a message that references actual task names and counts.
    Falls back to generic templates if no task context is available.
    """
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

    return _pick_message(nudge_type, strictness)


def _within_time_window(allowed_windows: list[dict]) -> bool:
    """True if current local time falls within any allowed window, or no windows defined."""
    if not allowed_windows:
        return True
    now = datetime.now().time()
    for window in allowed_windows:
        try:
            start = time.fromisoformat(window["start"])
            end = time.fromisoformat(window["end"])
            if start <= now <= end:
                return True
        except (KeyError, ValueError):
            continue
    return False


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

    oldest_title = None
    oldest_days = None
    for t in overdue:
        dd = t.get("due_date")
        if dd:
            try:
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


def _build_candidates(
    insight: dict,
    user_context: dict,
    strictness: float,
) -> list[dict]:
    """
    Step 1-3: Apply decision rules to produce candidate nudges.
    - One candidate per nudge type (type-level dedup within a single call).
    - relies entirely on boolean decision_signals from the insight object.
    """
    signals = insight.get("decision_signals", {})
    if not isinstance(signals, dict):
        signals = {}

    seen_types: set[str] = set()
    candidates: list[dict] = []

    # Map signals to actions
    triggers = []
    
    if signals.get("needs_correction"):
        triggers.append(("correction", "high"))
    elif signals.get("has_overdue_tasks"):
        triggers.append(("correction", "high"))
        
    if signals.get("goal_at_risk"):
        triggers.append(("strategic", "medium"))
        
    if signals.get("needs_activation"):
        triggers.append(("activation", "low"))
        
    # the orchestrator injects 'evening_reflection' into behavior_flags originally,
    # to maintain evening reflection, we'll check it, though ideally it moves to signals
    if "evening_reflection" in insight.get("behavior_flags", []):
        triggers.append(("reflection", "low"))

    task_ctx = _get_task_context(user_context)

    for nudge_type, priority in triggers:
        if nudge_type in seen_types:
            continue
        seen_types.add(nudge_type)

        message = _pick_task_aware_message(nudge_type, task_ctx, strictness)

        candidates.append({
            "type":     nudge_type,
            "message":  message,
            "priority": priority,
            "timing":   "immediate",
        })

    return candidates


# ---------------------------------------------------------------------------
# Public API  (per CONTRACT.md)
# ---------------------------------------------------------------------------

def generate_nudges(
    insight: dict,
    user_context: dict,
    history: dict,
    preferences: dict,
) -> list[dict]:
    """
    Generate nudges from a behavioral insight, user context, nudge history,
    and user preferences.

    Parameters
    ----------
    insight : dict
        Keys: summary (str), behavior_flags (list[str]), goal_alignment (float 0-1)

    user_context : dict
        Current state of the user (flexible schema, passed through to future rules).

    history : dict
        Keys:
          nudges_sent_today (int)  — how many nudges were sent today
          last_nudge_time   (str)  — ISO timestamp of last nudge (optional)
          recent_nudges     (list) — list of recent Nudge objects (used for dedup)

    preferences : dict
        Keys:
          max_nudges_per_day (int,   default 3)
          strictness         (float, default 0.7)
          allowed_time_windows (list[dict], optional)

    Returns
    -------
    list[dict] — up to 2 nudges, each with: type, message, priority, timing.
    Returns [] if daily limit is reached or no triggers fire.

    Guarantees (CONTRACT.md)
    ------------------------
    - max 2 nudges per call
    - no duplicate nudge types against recent_nudges in history
    - respects max_nudges_per_day
    """

    # --- Extract history ---
    sent_today: int = int(history.get("nudges_sent_today", 0))
    recent_nudges: list = history.get("recent_nudges", [])
    recent_types: set[str] = {
        n.get("type") for n in recent_nudges if isinstance(n, dict)
    }

    # --- Extract preferences ---
    max_per_day: int      = int(preferences.get("max_nudges_per_day", 3))
    strictness: float     = float(preferences.get("strictness", 0.7))
    allowed_windows: list = preferences.get("allowed_time_windows", [])

    # --- Daily limit gate ---
    if sent_today >= max_per_day:
        return []

    slots_remaining = max_per_day - sent_today
    max_this_call   = min(2, slots_remaining)  # CONTRACT: max 2 per call

    # --- Step 1-3: Build candidates ---
    candidates = _build_candidates(insight, user_context, strictness)
    if not candidates:
        return []

    # --- Step 6 (Guide): Dedup against history (no duplicate nudge types) ---
    candidates = [c for c in candidates if c["type"] not in recent_types]
    if not candidates:
        return []

    # --- Sort by priority (high first) ---
    candidates.sort(key=lambda n: PRIORITY_ORDER.get(n["priority"], 3))

    # --- Determine timing for each ---
    in_window = _within_time_window(allowed_windows)
    for nudge in candidates:
        nudge["timing"] = "immediate" if in_window else "scheduled"

    # --- Suppress low-priority if only 1 slot left ---
    if slots_remaining == 1:
        candidates = [c for c in candidates if c["priority"] != "low"]

    return candidates[:max_this_call]
