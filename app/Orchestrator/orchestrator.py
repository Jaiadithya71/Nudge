"""
orchestrator.py — Public API for the Orchestrator module.

Exports:
    run_scheduler(user_id, mode, preferences)   — blocking scheduler loop
    run_job(user_id, job_type, mode, preferences) — execute one job immediately

Internal pipeline for each job (per IMPLEMENTATION_GUIDE.md):
    context = memory.build_user_context(user_id)
    insight = llm.generate_insight(context_dict, mode)
    nudges  = nudge.generate_nudges(insight, context_dict, history, preferences)

Job types (CONTRACT.md):
    morning  — build context → insight → planning nudges          (~07:00)
    midday   — check inactivity → activation nudge               (~12:00)
    evening  — build context → reflection nudge                  (~19:00)
    event    — on-demand, no time check (overdue / meeting-done)
"""

from __future__ import annotations

import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Inject sibling module paths so we can import Memory, LLM, and Remind
# without installing them as packages.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_NUDGE_ROOT = _HERE.parent  # .../Nudge/

_SIBLING_PATHS = [
    str(_NUDGE_ROOT / "Memory"),
    str(_NUDGE_ROOT / "llm_module"),
    str(_NUDGE_ROOT / "Remind"),
    str(_NUDGE_ROOT / "input"),
    str(_NUDGE_ROOT),          # exposes notification_service at project root
]
for _p in _SIBLING_PATHS:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Module-level imports (after path setup)
# ---------------------------------------------------------------------------
import uuid as _uuid

import state as _state

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Job schedule definitions
# ---------------------------------------------------------------------------

_JOB_SCHEDULE: list[tuple[str, tuple[int, int]]] = [
    ("morning", (7, 0)),
    ("midday",  (12, 0)),
    ("evening", (19, 0)),
]

# Rate-limit defaults (match CONTRACT.md / IMPLEMENTATION_GUIDE.md)
_DEFAULT_PREFERENCES = {
    "max_nudges_per_day": 3,
    "strictness": 0.7,
    "allowed_time_windows": [],
    "min_gap_hours": 2,        # Not in nudge engine yet — enforced here
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _current_time() -> tuple[int, int]:
    """Return (hour, minute) in UTC."""
    now = datetime.now(_UTC)
    return now.hour, now.minute


def _job_due(job_hour: int, job_min: int, hour: int, minute: int) -> bool:
    """True if current time is within a 1-minute window of the target time."""
    return hour == job_hour and minute == job_min


def _min_gap_elapsed(user_id: str, min_gap_hours: float) -> bool:
    """Return True if enough time has passed since the last nudge."""
    history = _state.get_history(user_id)
    last_ts = history.get("last_nudge_time")
    if last_ts is None:
        return True
    try:
        last_dt = datetime.fromisoformat(last_ts)
        elapsed = (datetime.now(_UTC) - last_dt).total_seconds() / 3600
        return elapsed >= min_gap_hours
    except ValueError:
        return True


def _context_to_llm_dict(context) -> dict:
    """
    Convert the Pydantic UserContext returned by memory.build_user_context()
    into the flat dict expected by llm_module.generate_insight().

    LLM UserContext schema (from llm_module/schemas.py):
        goals:             List[str]
        tasks:             List[dict]
        recent_actions:    List[str]
        behavior_patterns: List[str]
        daily_summary:     str
    """
    # Handle both Pydantic model and raw dict inputs
    if hasattr(context, "model_dump"):
        data = context.model_dump()
    elif hasattr(context, "dict"):
        data = context.dict()
    elif isinstance(context, dict):
        data = context
    else:
        raise TypeError(f"Unsupported context type: {type(context)}")

    goals = [
        g.get("title", "") if isinstance(g, dict) else str(g)
        for g in data.get("goals", [])
    ]

    tasks = [
        {
            "id": t.get("id", ""),
            "title": t.get("title", ""),
            "status": t.get("status", "pending"),
            "due_date": str(t.get("due_date", "")),
        }
        if isinstance(t, dict) else {"title": str(t)}
        for t in data.get("tasks", [])
    ]

    recent_actions = [
        a.get("action_type", "") if isinstance(a, dict) else str(a)
        for a in data.get("recent_actions", [])
    ]

    behavior_patterns = [
        bp.get("description", "") if isinstance(bp, dict) else str(bp)
        for bp in data.get("behavior_patterns", [])
    ]

    overdue = [t for t in tasks if t.get("status") == "overdue"]
    pending  = [t for t in tasks if t.get("status") == "pending"]
    daily_summary = (
        f"User has {len(goals)} goal(s), {len(tasks)} task(s) "
        f"({len(overdue)} overdue, {len(pending)} pending), "
        f"and {len(recent_actions)} recent action(s)."
    )

    return {
        "goals": goals,
        "tasks": tasks,
        "recent_actions": recent_actions,
        "behavior_patterns": behavior_patterns,
        "daily_summary": daily_summary,
    }


def _context_to_nudge_dict(context) -> dict:
    """Convert Pydantic UserContext to a plain dict for nudge_engine.generate_nudges()."""
    if hasattr(context, "model_dump"):
        return context.model_dump(mode="json")
    elif hasattr(context, "dict"):
        return context.dict()
    elif isinstance(context, dict):
        return context
    return {}


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _load_user_preferences(user_id: str) -> dict:
    """Load preferences from DB, fall back to defaults if unavailable."""
    try:
        import memory as mem
        return mem.get_preferences(user_id)
    except Exception as exc:
        logger.warning("Could not load user preferences (%s) — using defaults.", exc)
        return {}


def _build_context(user_id: str):
    """Call memory.build_user_context(). Returns Pydantic UserContext or mock dict."""
    try:
        import memory as mem
        return mem.build_user_context(user_id)
    except Exception as exc:
        logger.warning("memory.build_user_context failed (%s) — using empty context.", exc)
        return {
            "user_id": user_id,
            "goals": [], "tasks": [], "events": [],
            "contacts": [], "behavior_patterns": [],
            "goal_alignments": [], "recent_actions": [],
        }


def _generate_insight(context_llm_dict: dict, mode: str = "mock") -> Optional[dict]:
    """Call llm_module.generate_insight(). Returns Insight dict or None on failure."""
    try:
        from llm_module import generate_insight
        return generate_insight(context_llm_dict, mode=mode)
    except Exception as exc:
        logger.warning("llm_module.generate_insight failed (%s) — skipping insight.", exc)
        return None


def _generate_nudges(insight: dict, context_dict: dict, history: dict, preferences: dict) -> list[dict]:
    """Call nudge_engine.generate_nudges(). Returns list of nudge dicts."""
    try:
        import nudge_engine as ne
        return ne.generate_nudges(insight, context_dict, history, preferences)
    except Exception as exc:
        logger.warning("nudge_engine.generate_nudges failed (%s) — returning [].", exc)
        return []


# ---------------------------------------------------------------------------
# Job executors
# ---------------------------------------------------------------------------


def _log_context(job: str, user_id: str, context) -> None:
    """Emit a structured context log line."""
    try:
        data = context.model_dump() if hasattr(context, "model_dump") else context
        tasks = data.get("tasks", [])
        overdue = [t for t in tasks if (t.get("status") if isinstance(t, dict) else "") == "overdue"]
        logger.info(
            "[%s][context] user=%s tasks=%d overdue=%d goals=%d patterns=%d",
            job, user_id, len(tasks), len(overdue),
            len(data.get("goals", [])), len(data.get("behavior_patterns", [])),
        )
    except Exception:
        pass


def _log_signals(job: str, user_id: str, insight: dict) -> None:
    """Emit a structured decision-signals log line."""
    ds = insight.get("decision_signals", {})
    active = [k for k, v in ds.items() if v]
    logger.info("[%s][signals] user=%s active=%s", job, user_id, active or "none")


def _log_nudges(job: str, user_id: str, nudges: list[dict]) -> None:
    """Emit a structured nudge-output log line."""
    summary = [(n.get("type"), n.get("priority")) for n in nudges]
    logger.info("[%s][nudges] user=%s generated=%d %s", job, user_id, len(nudges), summary)


def _send_notifications(user_id: str, nudges: list[dict]) -> None:
    """Best-effort notification delivery (Web Push + Telegram) — failure never blocks the pipeline."""
    try:
        import notification_service as ns
        for nudge in nudges:
            ns.send_notification(user_id, nudge)
    except Exception as exc:
        logger.warning("[notify] Delivery skipped: %s", exc)


def _build_nudge_bank(insight: dict, strictness: float, context=None) -> list[dict]:
    """
    Generate one nudge per type to fill the day's bank.
    Uses task-aware messages when task context is available.
    """
    import nudge_engine as ne

    type_map = [
        ("correction",  "high"),
        ("strategic",   "medium"),
        ("activation",  "low"),
        ("reflection",  "low"),
        ("reminder",    "medium"),
    ]

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


def _run_morning_job(user_id: str, mode: str, preferences: dict) -> list[dict]:
    """
    Morning Job pipeline:
        build context → LLM insight (once/day) → fill nudge bank → cache both
        All subsequent nudge requests are served from the bank — no more LLM calls today.
    """
    logger.info("[morning] Starting pipeline for user=%s", user_id)

    context = _build_context(user_id)
    if not context:
        logger.info("[morning] No context — aborting.")
        return []
    _log_context("morning", user_id, context)

    context_llm = _context_to_llm_dict(context)
    insight = _generate_insight(context_llm, mode=mode)
    if not insight:
        logger.info("[morning] No insight — aborting.")
        return []
    _log_signals("morning", user_id, insight)

    # Cache the insight for the whole day
    _state.store_insight_cache(user_id, insight)
    logger.info("[morning] Insight cached for today")

    # Snapshot today's overdue count for the evaluation endpoint
    ctx_data = context.model_dump() if hasattr(context, "model_dump") else context
    _tasks = ctx_data.get("tasks", [])
    _overdue_count = len([t for t in _tasks if (t.get("status") if isinstance(t, dict) else "") == "overdue"])
    _state.store_kv(user_id, "daily_overdue_snapshot", str(_overdue_count))
    logger.info("[morning] Overdue snapshot stored: %d", _overdue_count)

    # Generate full nudge bank (all types) — served throughout the day
    strictness = preferences.get("strictness", 0.7)
    bank = _build_nudge_bank(insight, strictness, context=context)
    _state.store_nudge_bank(user_id, bank)
    logger.info("[morning] Nudge bank stored: %d nudge(s) — types=%s",
                len(bank), [n.get("type") for n in bank])

    # Return the highest-priority nudge for immediate morning delivery
    context_dict = _context_to_nudge_dict(context)
    history = _state.get_history(user_id)
    nudges = _generate_nudges(insight, context_dict, history, preferences)

    # In TEST_MODE: dedup fills up fast across re-runs — fall back to top bank nudge
    import os as _os
    if not nudges and bank and _os.environ.get("TEST_MODE", "").lower() in ("true", "1", "yes"):
        nudges = [bank[0]]
        logger.info("[morning][test_mode] Dedup blocked all candidates — using top bank nudge")

    _log_nudges("morning", user_id, nudges)
    return nudges


def _run_midday_job(user_id: str, mode: str, preferences: dict) -> list[dict]:
    """
    Midday Job pipeline:
        detect inactivity → generate activation nudge (skips full context build)
    """
    logger.info("[midday] Checking inactivity for user=%s", user_id)

    # Minimal synthetic insight that triggers the activation nudge type
    inactivity_insight = {
        "insight_id": "midday-inactivity",
        "summary": "Midday check — user may be inactive.",
        "key_observations": ["Midday check triggered"],
        "goal_alignment": "0.5",
        "behavior_flags": ["inactivity"],
        "opportunity_areas": ["re-engage with pending tasks"],
        "decision_signals": {
            "needs_activation": True,
            "needs_correction": False,
            "goal_at_risk": False,
            "has_overdue_tasks": False
        }
    }

    context = _build_context(user_id)
    _log_context("midday", user_id, context)
    context_dict = _context_to_nudge_dict(context)
    history = _state.get_history(user_id)

    nudges = _generate_nudges(inactivity_insight, context_dict, history, preferences)
    _log_nudges("midday", user_id, nudges)
    return nudges


def _run_evening_job(user_id: str, mode: str, preferences: dict) -> list[dict]:
    """
    Evening Job pipeline:
        build context → generate reflection insight → generate reflection nudge
    """
    logger.info("[evening] Starting pipeline for user=%s", user_id)

    context = _build_context(user_id)
    _log_context("evening", user_id, context)
    context_llm = _context_to_llm_dict(context)
    insight = _generate_insight(context_llm, mode=mode)
    if not insight:
        logger.info("[evening] No insight — aborting.")
        return []
    _log_signals("evening", user_id, insight)

    if isinstance(insight.get("behavior_flags"), list):
        insight["behavior_flags"].append("evening_reflection")
    else:
        insight["behavior_flags"] = ["evening_reflection"]

    context_dict = _context_to_nudge_dict(context)
    history = _state.get_history(user_id)
    evening_preferences = {**preferences, "strictness": 0.4}

    nudges = _generate_nudges(insight, context_dict, history, evening_preferences)
    _log_nudges("evening", user_id, nudges)
    return nudges


def _run_event_job(user_id: str, mode: str, preferences: dict, event_type: Optional[str] = None) -> list[dict]:
    """
    Event-Based Job:
        Triggered on-demand (overdue task, meeting completed, etc.)
        Builds context and runs the full insight → nudge pipeline.
    """
    logger.info("[event] Event=%s triggered for user=%s", event_type, user_id)

    context = _build_context(user_id)
    _log_context("event", user_id, context)
    context_llm = _context_to_llm_dict(context)
    insight = _generate_insight(context_llm, mode=mode)
    if not insight:
        logger.info("[event] No insight — aborting.")
        return []
    _log_signals("event", user_id, insight)

    context_dict = _context_to_nudge_dict(context)
    history = _state.get_history(user_id)
    nudges = _generate_nudges(insight, context_dict, history, preferences)
    _log_nudges("event", user_id, nudges)
    return nudges


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_JOB_RUNNERS = {
    "morning": _run_morning_job,
    "midday":  _run_midday_job,
    "evening": _run_evening_job,
    "event":   _run_event_job,
}


def run_job(
    user_id: str,
    job_type: str,
    mode: str = "mock",
    preferences: Optional[dict] = None,
    **kwargs,
) -> list[dict]:
    """
    Execute a single Orchestrator job for *user_id*.

    Parameters
    ----------
    user_id   : str   — identifies the user
    job_type  : str   — one of: morning | midday | evening | event
    mode      : str   — "mock" (no API calls) or "real" (calls Gemini)
    preferences : dict — overrides for max_nudges_per_day, strictness, etc.

    Returns
    -------
    list[dict] — nudges produced by this job (may be empty)
    """
    if not user_id:
        raise ValueError("user_id is required")
    if job_type not in _JOB_RUNNERS:
        raise ValueError(f"Unknown job_type {job_type!r}. Must be one of: {list(_JOB_RUNNERS)}")

    # Merge: defaults < DB preferences < caller-supplied overrides
    db_prefs  = _load_user_preferences(user_id)
    prefs = {
        **_DEFAULT_PREFERENCES,
        "max_nudges_per_day": db_prefs.get("max_nudges_per_day", _DEFAULT_PREFERENCES["max_nudges_per_day"]),
        "min_gap_hours":      db_prefs.get("min_gap_hours",      _DEFAULT_PREFERENCES["min_gap_hours"]),
        "strictness":         db_prefs.get("strictness",         _DEFAULT_PREFERENCES["strictness"]),
        **(preferences or {}),
    }
    min_gap = prefs.pop("min_gap_hours", 2)

    # --- Rate-limit gate ---
    history = _state.get_history(user_id)
    if history["nudges_sent_today"] >= prefs["max_nudges_per_day"]:
        logger.info("Daily limit reached for user=%s — skipping %s job.", user_id, job_type)
        _state.update_after_run(user_id, job_type)
        return []

    if not _min_gap_elapsed(user_id, min_gap):
        logger.info(
            "Min-gap of %sh not elapsed for user=%s — skipping %s job.",
            min_gap, user_id, job_type,
        )
        _state.update_after_run(user_id, job_type)
        return []

    # --- Execute the appropriate pipeline ---
    runner = _JOB_RUNNERS[job_type]
    nudges = runner(user_id, mode, prefs, **kwargs)

    # --- Pre-assign IDs so Telegram callbacks can reference them ---
    for nudge in nudges:
        if not nudge.get("id"):
            nudge["id"] = str(_uuid.uuid4())

    # --- Push notifications proactively (do not wait for /api/nudges) ---
    _send_notifications(user_id, nudges)

    # --- Update state ---
    _state.update_after_run(user_id, job_type)
    _state.record_nudges(user_id, nudges, job_type)

    return nudges


def _run_per_task_nudges(user_id: str, current_hm: str, last_fired: dict) -> None:
    """
    Check for tasks due for a nudge at current_hm, respecting nudge_times array
    and nudge_days weekday filter.
    Deduped per task_id so a task only fires once per minute.
    """
    from datetime import datetime as _dt
    day_abbrev = _dt.now().strftime("%a").lower()  # "mon", "tue", etc.
    try:
        import memory as mem
        tasks = mem.get_tasks_due_for_nudge(user_id, current_hm, day_abbrev=day_abbrev)
    except Exception as exc:
        logger.warning("[per-task] Could not load tasks: %s", exc)
        return

    if not tasks:
        return

    for task in tasks:
        task_id  = task.get("id", "unknown")
        fire_key = f"task:{task_id}:{current_hm}"
        if last_fired.get(fire_key):
            continue  # already fired this minute

        message = task.get("nudge_message") or f"Reminder: {task.get('title', 'a task')} needs your attention."
        nudge = {
            "id":       str(_uuid.uuid4()),
            "type":     "reminder",
            "message":  message,
            "priority": "high" if task.get("status") == "overdue" else "medium",
            "timing":   "immediate",
        }

        logger.info("[per-task] Firing nudge: task=%s title=%r time=%s", task_id, task.get("title"), current_hm)
        _send_notifications(user_id, [nudge])
        _state.record_nudges(user_id, [nudge], job_type="per-task")
        last_fired[fire_key] = current_hm


def run_scheduler(
    user_id: str,
    mode: str = "mock",
    preferences: Optional[dict] = None,
    poll_interval_seconds: int = 60,
    _time_fn=None,
) -> None:
    """
    Blocking scheduler loop for *user_id*.

    Normal mode: checks the current time every poll_interval_seconds and fires
    the appropriate job when the clock matches a scheduled window.

    TEST_MODE (env TEST_MODE=true): ignores the clock and runs the morning job
    every TEST_MODE_INTERVAL_MINUTES minutes (default 5).

    Parameters
    ----------
    user_id              : str  — identifies the user
    mode                 : str  — "mock" or "real"
    preferences          : dict — forwarded to run_job()
    poll_interval_seconds: int  — how often to check the time (default 60 s)
    _time_fn             : callable — injectable time source (used in tests)
    """
    import os as _os

    if not user_id:
        raise ValueError("user_id is required")

    test_mode = _os.environ.get("TEST_MODE", "").lower() in ("true", "1", "yes")

    if test_mode:
        interval_min = int(_os.environ.get("TEST_MODE_INTERVAL_MINUTES", "5"))
        interval_sec = interval_min * 60
        # Bypass rate limits in test mode so every interval fires a real job
        test_prefs = {**(preferences or {}), "min_gap_hours": 0, "max_nudges_per_day": 999}
        logger.info(
            "Scheduler started in TEST_MODE for user=%s (mode=%s, interval=%dm)",
            user_id, mode, interval_min,
        )
        while True:
            logger.info("[test_mode] Triggering morning job for user=%s", user_id)
            try:
                run_job(user_id, "morning", mode=mode, preferences=test_prefs)
            except Exception as exc:
                logger.error("[test_mode] Morning job failed: %s", exc)
            time.sleep(interval_sec)

    # Normal mode — time-based scheduling
    _last_fired: dict[str, str] = {}   # job_type -> "HH:MM" when it last ran

    logger.info("Scheduler started for user=%s (mode=%s)", user_id, mode)

    while True:
        hour, minute = _time_fn() if _time_fn else _current_time()
        current_hm = f"{hour:02d}:{minute:02d}"

        # Re-read user preferences each cycle so time changes take effect immediately
        db_prefs = _load_user_preferences(user_id)
        def _t(key: str, fallback: str) -> tuple[int, int]:
            val = db_prefs.get(key, fallback)
            try:
                h, m = str(val).split(":")
                return int(h), int(m)
            except Exception:
                h, m = fallback.split(":")
                return int(h), int(m)

        live_schedule = [
            ("morning", _t("morning_time", "07:00")),
            ("midday",  _t("midday_time",  "12:00")),
            ("evening", _t("evening_time", "19:00")),
        ]

        for job_type, (job_hour, job_min) in live_schedule:
            if _job_due(job_hour, job_min, hour, minute):
                if _last_fired.get(job_type) != current_hm:
                    logger.info("Triggering %s job at %s for user=%s", job_type, current_hm, user_id)
                    try:
                        run_job(user_id, job_type, mode=mode, preferences=preferences)
                    except Exception as exc:
                        logger.error("Job %s failed: %s", job_type, exc)
                    _last_fired[job_type] = current_hm

        # Per-task nudge check — fires for tasks with nudge_time matching right now
        _run_per_task_nudges(user_id, current_hm, _last_fired)

        time.sleep(poll_interval_seconds)
