import logging

# Ensure dependencies are loaded to fix sys.path first!
from api import dependencies

import memory as mem
from llm_module import generate_insight
import nudge_engine as ne
import orchestrator as orch

logger = logging.getLogger(__name__)


def get_context(user_id: str) -> dict:
    """Fetch the user's current context from memory (no ingestion — call /sync first)."""
    try:
        context = mem.build_user_context(user_id)
        raw = context.model_dump(mode="json") if hasattr(context, "model_dump") else context
        tasks = raw.get("tasks", [])
        overdue = [t for t in tasks if t.get("status") == "overdue"]
        pending  = [t for t in tasks if t.get("status") == "pending"]
        logger.info(
            "[context] user=%s tasks=%d overdue=%d pending=%d goals=%d actions=%d patterns=%d",
            user_id, len(tasks), len(overdue), len(pending),
            len(raw.get("goals", [])),
            len(raw.get("recent_actions", [])),
            len(raw.get("behavior_patterns", [])),
        )
        return raw
    except Exception as e:
        logger.error("[context] user=%s error=%s", user_id, e)
        return {"error": str(e)}


def _build_llm_context(raw_context: dict) -> dict:
    """Mirror orchestrator._context_to_llm_dict: flatten Pydantic context into the LLM-expected shape."""
    goals = [g.get("title", "") if isinstance(g, dict) else str(g) for g in raw_context.get("goals", [])]
    tasks = [
        {"id": t.get("id", ""), "title": t.get("title", ""), "status": t.get("status", "pending"), "due_date": str(t.get("due_date", ""))}
        if isinstance(t, dict) else {"title": str(t)}
        for t in raw_context.get("tasks", [])
    ]
    recent_actions = [a.get("action_type", "") if isinstance(a, dict) else str(a) for a in raw_context.get("recent_actions", [])]
    behavior_patterns = [bp.get("description", "") if isinstance(bp, dict) else str(bp) for bp in raw_context.get("behavior_patterns", [])]
    overdue = [t for t in tasks if t.get("status") == "overdue"]
    pending  = [t for t in tasks if t.get("status") == "pending"]
    daily_summary = (
        f"User has {len(goals)} goal(s), {len(tasks)} task(s) "
        f"({len(overdue)} overdue, {len(pending)} pending), "
        f"and {len(recent_actions)} recent action(s)."
    )
    return {"goals": goals, "tasks": tasks, "recent_actions": recent_actions, "behavior_patterns": behavior_patterns, "daily_summary": daily_summary}


def _evaluate_signals_locally(context: dict) -> dict:
    """
    Derive decision signals from raw context without calling the LLM.
    Used for bank-based nudge selection throughout the day.
    """
    tasks = context.get("tasks", [])
    overdue = [t for t in tasks if isinstance(t, dict) and t.get("status") == "overdue"]
    goals = context.get("goals", [])
    return {
        "needs_correction":  len(overdue) > 0,
        "has_overdue_tasks": len(overdue) > 0,
        "needs_activation":  len(tasks) == 0,
        "goal_at_risk":      len(goals) > 0 and len(tasks) < 2,
    }


def get_insight(user_id: str, mode: str = "mock") -> dict:
    # Serve from cache if available (avoids LLM call after morning job)
    try:
        import state as _state
        cached = _state.get_cached_insight(user_id)
        if cached:
            logger.info("[insight] user=%s served from cache", user_id)
            return cached
    except Exception:
        pass

    context = get_context(user_id)
    if "error" in context:
        return {"error": "Failed to load context for insight."}
    try:
        llm_context = _build_llm_context(context)
        insight = generate_insight(llm_context, mode=mode)
        if not insight:
            return {"error": "Insight generation returned Null"}
        ds = insight.get("decision_signals", {})
        is_fallback = not any(ds.values())
        logger.info(
            "[insight] user=%s mode=%s fallback=%s signals=%s",
            user_id, mode, is_fallback, dict(ds),
        )
        # Cache this fresh insight so subsequent calls skip the LLM
        try:
            _state.store_insight_cache(user_id, insight)
        except Exception:
            pass
        return insight
    except Exception as e:
        logger.error("[insight] user=%s error=%s", user_id, e)
        return {"error": str(e)}


def get_nudges(user_id: str, mode: str = "mock") -> list:
    try:
        import state as _state
        history = _state.get_history(user_id)
    except Exception:
        history = {}

    max_per_day = 5
    sent_today = history.get("nudges_sent_today", 0)
    if sent_today >= max_per_day:
        logger.info("[nudges] user=%s daily limit reached (%d/%d)", user_id, sent_today, max_per_day)
        return []

    # Try serving from today's nudge bank first (no LLM needed)
    try:
        bank = _state.get_nudge_bank(user_id)
    except Exception:
        bank = []

    if bank:
        signals = _evaluate_signals_locally(get_context(user_id))
        recent_types = {n.get("type") for n in history.get("recent_nudges", [])}

        # Signal-matched types go first; remaining bank types follow (still valid for today)
        signal_to_types = {
            "needs_correction":  "correction",
            "has_overdue_tasks": "correction",
            "goal_at_risk":      "strategic",
            "needs_activation":  "activation",
        }
        prioritised = {t for sig, t in signal_to_types.items() if signals.get(sig)}
        from datetime import datetime
        if datetime.now().hour >= 18:
            prioritised.add("reflection")

        type_priority = {t: i for i, t in enumerate(
            ["correction", "strategic", "activation", "reflection", "reminder"]
        )}

        # All bank types are eligible — sort by: signal-matched first, then type priority
        candidates = [
            n for n in bank if n.get("type") not in recent_types
        ]
        candidates.sort(key=lambda n: (
            0 if n.get("type") in prioritised else 1,
            type_priority.get(n.get("type", ""), 99),
        ))

        slots = min(2, max_per_day - sent_today)
        nudges = candidates[:slots]

        logger.info(
            "[nudges] user=%s source=bank prioritised=%s selected=%d sent_today=%d/%d",
            user_id, list(prioritised), len(nudges), sent_today, max_per_day,
        )
        if nudges:
            _state.record_nudges(user_id, nudges, job_type="api")
        return nudges

    # No bank yet (morning job hasn't run) — fall back to live LLM path
    logger.info("[nudges] user=%s no bank found — falling back to live insight", user_id)
    insight = get_insight(user_id, mode)
    if "error" in insight:
        return []

    if mode == "real":
        ds = insight.get("decision_signals", {})
        if not any(ds.values()):
            logger.warning("[nudges] user=%s real LLM fallback — switching to mock", user_id)
            insight = get_insight(user_id, "mock")

    context = get_context(user_id)
    preferences = {"max_nudges_per_day": max_per_day, "strictness": 0.5, "allowed_time_windows": [], "min_gap_hours": 0}

    try:
        nudges = ne.generate_nudges(insight, context, history, preferences)
        logger.info(
            "[nudges] user=%s source=live generated=%d types=%s sent_today=%d/%d",
            user_id, len(nudges), [n.get("type") for n in nudges], sent_today, max_per_day,
        )
        return nudges
    except Exception as e:
        logger.error("[nudges] user=%s error=%s", user_id, e)
        return []


def log_action(user_id: str, action: str, metadata: dict) -> dict:
    try:
        action_payload = {
            "action_type": action,
            "entity_type": "api",
            "metadata": metadata
        }
        mem.log_action(user_id, action_payload)
        logger.info("[action] user=%s action=%s", user_id, action)
        return {"status": "success", "message": f"Logged action '{action}'"}
    except Exception as e:
        logger.error("[action] user=%s error=%s", user_id, e)
        return {"error": str(e)}


def get_evaluation_data(user_id: str) -> dict:
    """
    Compute today's nudge performance metrics from nudge_log and user_actions.
    Serves GET /api/evaluation/today.
    """
    try:
        import db
        from datetime import date

        today = date.today().isoformat()
        conn  = db.get_connection(user_id)
        try:
            # Nudges sent today
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM nudge_log WHERE date(sent_at) = ?", (today,)
            ).fetchone()
            nudges_sent = row["cnt"] if row else 0

            # Nudge type breakdown
            rows = conn.execute(
                "SELECT type, COUNT(*) as cnt FROM nudge_log "
                "WHERE date(sent_at) = ? GROUP BY type", (today,)
            ).fetchall()
            nudge_breakdown = {r["type"]: r["cnt"] for r in rows}

            # User responses to nudges today
            rows = conn.execute(
                "SELECT action_type, COUNT(*) as cnt FROM user_actions "
                "WHERE entity_type = 'nudge' AND date(created_at) = ? "
                "GROUP BY action_type", (today,)
            ).fetchall()
            response_counts = {r["action_type"]: r["cnt"] for r in rows}

            acknowledged = response_counts.get("acknowledged", 0)
            snoozed      = response_counts.get("snoozed", 0)
            ignored      = response_counts.get("ignored", 0)
            total_responses = acknowledged + snoozed + ignored

            response_rate = round(total_responses / nudges_sent, 2) if nudges_sent else 0.0
            ignore_rate   = round(ignored / nudges_sent, 2) if nudges_sent else 0.0

            # Current overdue task count
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM tasks WHERE status = 'overdue'"
            ).fetchone()
            overdue_now = row["cnt"] if row else 0

        finally:
            conn.close()

        # Morning snapshot (stored by orchestrator during morning job)
        import state as _state
        snapshot_str      = _state.get_kv(user_id, "daily_overdue_snapshot")
        overdue_before    = int(snapshot_str) if snapshot_str and snapshot_str.isdigit() else overdue_now
        overdue_delta     = overdue_before - overdue_now  # positive = tasks resolved

        return {
            "nudges_sent":          nudges_sent,
            "acknowledged":         acknowledged,
            "snoozed":              snoozed,
            "ignored":              ignored,
            "response_rate":        response_rate,
            "ignore_rate":          ignore_rate,
            "overdue_tasks_before": overdue_before,
            "overdue_tasks_after":  overdue_now,
            "overdue_delta":        overdue_delta,
            "nudge_breakdown":      nudge_breakdown,
        }

    except Exception as e:
        logger.error("[evaluation] user=%s error=%s", user_id, e)
        return {"error": str(e)}


def run_cycle(user_id: str, job_type: str = "morning", mode: str = "mock") -> dict:
    try:
        preferences = {"max_nudges_per_day": 5, "strictness": 0.5, "allowed_time_windows": [], "min_gap_hours": 0}
        nudges = orch.run_job(user_id, job_type, mode, preferences)
        logger.info("[cycle] user=%s job=%s mode=%s nudges=%d", user_id, job_type, mode, len(nudges))
        return {"status": "success", "job_type": job_type, "nudges_generated": len(nudges), "nudges": nudges}
    except Exception as e:
        logger.error("[cycle] user=%s job=%s error=%s", user_id, job_type, e)
        return {"error": str(e)}
