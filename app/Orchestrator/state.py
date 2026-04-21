"""
state.py — Per-user state management for the Orchestrator.

State is persisted to the per-user SQLite DB (Memory module, same mirror.db).
Survives server restarts. Daily nudge counts are derived from nudge_log rows,
so no manual daily-reset logic is needed.

Tables used (defined in Memory/schema.sql):
    nudge_log          — one row per nudge sent; queried for counts + dedup
    orchestrator_state — key/value store for last_run, last_run_job
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, date

_UTC = timezone.utc
_RECENT_NUDGES_LIMIT = 10  # rows returned for dedup against recent_nudges


def _now_iso() -> str:
    return datetime.now(_UTC).isoformat()


def _conn(user_id: str):
    """Return a SQLite connection for user_id via the Memory db module."""
    import db  # on sys.path via Orchestrator/orchestrator.py path injection
    return db.get_connection(user_id)


# ---------------------------------------------------------------------------
# Public API  (same interface as before — callers unchanged)
# ---------------------------------------------------------------------------

def get_state(user_id: str) -> dict:
    """Return the current state dict for user_id, derived from the DB."""
    conn = _conn(user_id)
    try:
        today = date.today().isoformat()

        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM nudge_log WHERE date(sent_at) = ?",
            (today,),
        ).fetchone()
        nudges_sent_today = row["cnt"] if row else 0

        row = conn.execute(
            "SELECT MAX(sent_at) as last FROM nudge_log"
        ).fetchone()
        last_nudge_time = row["last"] if row else None

        row = conn.execute(
            "SELECT value FROM orchestrator_state WHERE key = 'last_run'"
        ).fetchone()
        last_run = row["value"] if row else None

        row = conn.execute(
            "SELECT value FROM orchestrator_state WHERE key = 'last_run_job'"
        ).fetchone()
        last_run_job = row["value"] if row else None

        rows = conn.execute(
            "SELECT type, message, priority, timing FROM nudge_log "
            "WHERE date(sent_at) = ? ORDER BY sent_at DESC LIMIT ?",
            (today, _RECENT_NUDGES_LIMIT),
        ).fetchall()
        recent_nudges = [dict(r) for r in rows]

        return {
            "nudges_sent_today": nudges_sent_today,
            "last_nudge_time":   last_nudge_time,
            "last_run":          last_run,
            "last_run_job":      last_run_job,
            "recent_nudges":     recent_nudges,
        }
    finally:
        conn.close()


def get_history(user_id: str) -> dict:
    """Return the history dict expected by nudge_engine.generate_nudges()."""
    state = get_state(user_id)
    return {
        "nudges_sent_today": state["nudges_sent_today"],
        "last_nudge_time":   state["last_nudge_time"],
        "recent_nudges":     state["recent_nudges"],
    }


def update_after_run(user_id: str, job_type: str) -> None:
    """Record that a job just ran for user_id."""
    conn = _conn(user_id)
    try:
        now = _now_iso()
        conn.execute(
            "INSERT OR REPLACE INTO orchestrator_state (key, value, updated_at) "
            "VALUES (?, ?, ?)",
            ("last_run", now, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO orchestrator_state (key, value, updated_at) "
            "VALUES (?, ?, ?)",
            ("last_run_job", job_type, now),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Nudge bank  (pre-generated pool — one LLM call per day)
# ---------------------------------------------------------------------------

def get_nudge_bank(user_id: str) -> list[dict]:
    """Return today's nudge bank, or [] if not yet generated."""
    conn = _conn(user_id)
    try:
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT type, message, priority FROM nudge_bank WHERE for_date = ? ORDER BY created_at",
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def store_nudge_bank(user_id: str, nudges: list[dict]) -> None:
    """Replace today's bank with a fresh set of nudges."""
    conn = _conn(user_id)
    try:
        today = date.today().isoformat()
        conn.execute("DELETE FROM nudge_bank WHERE for_date = ?", (today,))
        for nudge in nudges:
            conn.execute(
                "INSERT INTO nudge_bank (id, type, message, priority, for_date) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), nudge.get("type", ""), nudge.get("message", ""),
                 nudge.get("priority", "medium"), today),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Insight cache  (stored in orchestrator_state as JSON, keyed by date)
# ---------------------------------------------------------------------------

def get_cached_insight(user_id: str) -> dict | None:
    """Return today's cached insight, or None if not yet generated."""
    conn = _conn(user_id)
    try:
        today = date.today().isoformat()
        row = conn.execute(
            "SELECT value FROM orchestrator_state WHERE key = 'insight_cache_date'"
        ).fetchone()
        if not row or row["value"] != today:
            return None
        row = conn.execute(
            "SELECT value FROM orchestrator_state WHERE key = 'insight_cache'"
        ).fetchone()
        return json.loads(row["value"]) if row else None
    finally:
        conn.close()


def store_insight_cache(user_id: str, insight: dict) -> None:
    """Cache today's insight in the DB."""
    conn = _conn(user_id)
    try:
        today = date.today().isoformat()
        now = _now_iso()
        for key, value in [
            ("insight_cache", json.dumps(insight)),
            ("insight_cache_date", today),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO orchestrator_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
        conn.commit()
    finally:
        conn.close()


def record_nudges(user_id: str, nudges: list[dict], job_type: str = "") -> None:
    """Persist generated nudges to nudge_log. Uses nudge['id'] if already set."""
    if not nudges:
        return
    conn = _conn(user_id)
    try:
        now = _now_iso()
        for nudge in nudges:
            nudge_id = nudge.get("id") or str(uuid.uuid4())
            conn.execute(
                "INSERT OR IGNORE INTO nudge_log "
                "(id, type, message, priority, timing, job_type, sent_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    nudge_id,
                    nudge.get("type", ""),
                    nudge.get("message", ""),
                    nudge.get("priority", ""),
                    nudge.get("timing", ""),
                    job_type,
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Generic key-value helpers  (used by evaluation snapshot, etc.)
# ---------------------------------------------------------------------------

def store_kv(user_id: str, key: str, value: str) -> None:
    """Write an arbitrary key-value pair to orchestrator_state."""
    conn = _conn(user_id)
    try:
        now = _now_iso()
        conn.execute(
            "INSERT OR REPLACE INTO orchestrator_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_kv(user_id: str, key: str) -> str | None:
    """Read a value from orchestrator_state. Returns None if key absent."""
    conn = _conn(user_id)
    try:
        row = conn.execute(
            "SELECT value FROM orchestrator_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()
