"""
memory.py — Public API for the Memory module.

Exports exactly the four functions defined in CONTRACT.md:
    - build_user_context(user_id) -> UserContext
    - log_action(user_id, action) -> None
    - ingest(entity_type, payload, user_id) -> None
    - semantic_search(user_id, query) -> list

Rules (from CONTRACT.md):
    - Always require user_id
    - Deterministic outputs
    - No schema leakage
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

_UTC = timezone.utc


def _now_iso() -> str:
    return datetime.now(_UTC).isoformat()

import db
import vector_db as vdb
from models import (
    BehaviorPattern,
    Contact,
    Event,
    Goal,
    GoalAlignment,
    Task,
    UserAction,
    UserContext,
)

# Entity types that are worth embedding for semantic search
_SEARCHABLE_ENTITY_TYPES = {"goals", "tasks", "contacts", "events"}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _rows(conn, table: str) -> list[dict]:
    """Fetch all rows from *table* as plain dicts."""
    cursor = conn.execute(f"SELECT * FROM {table}")  # noqa: S608
    return [dict(row) for row in cursor.fetchall()]


def _ensure_id(payload: dict) -> dict:
    """Inject a UUID id if not already present."""
    if "id" not in payload or not payload["id"]:
        payload = {**payload, "id": str(uuid.uuid4())}
    return payload


def _text_for_embedding(entity_type: str, payload: dict) -> str:
    """Build a plain-text representation for embedding."""
    parts = [entity_type.upper()]
    for key in ("title", "description", "name", "email", "pattern_type"):
        if payload.get(key):
            parts.append(str(payload[key]))
    return " | ".join(parts)


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def build_user_context(user_id: str) -> UserContext:
    """
    Build and return the UserContext for *user_id*.

    Reads from the user's isolated SQLite database. Returns a fully
    validated Pydantic model. No raw DB rows are exposed.
    """
    if not user_id:
        raise ValueError("user_id is required")

    conn = db.get_connection(user_id)
    try:
        goals         = [Goal(**r)            for r in _rows(conn, "goals")]
        tasks         = [Task(**r)            for r in _rows(conn, "tasks")]
        events        = [Event(**r)           for r in _rows(conn, "events")]
        contacts      = [Contact(**r)         for r in _rows(conn, "contacts")]
        patterns      = [BehaviorPattern(**r) for r in _rows(conn, "behavior_patterns")]
        alignments    = [GoalAlignment(**r)   for r in _rows(conn, "goal_alignment")]
        recent_actions = [
            UserAction(**r)
            for r in conn.execute(
                "SELECT * FROM user_actions ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        ]
    finally:
        db.close(conn)

    return UserContext(
        user_id=user_id,
        goals=goals,
        tasks=tasks,
        events=events,
        contacts=contacts,
        behavior_patterns=patterns,
        goal_alignments=alignments,
        recent_actions=recent_actions,
    )


def log_action(user_id: str, action: dict[str, Any]) -> None:
    """
    Persist an action record for *user_id*.

    *action* may contain: action_type, entity_type, entity_id, metadata.
    A UUID id and created_at timestamp are injected automatically.
    """
    if not user_id:
        raise ValueError("user_id is required")

    record = _ensure_id(action.copy())
    record.setdefault("created_at", _now_iso())

    # Serialise metadata to JSON string if it is a dict
    if isinstance(record.get("metadata"), dict):
        record["metadata"] = json.dumps(record["metadata"])

    conn = db.get_connection(user_id)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_actions
                (id, action_type, entity_type, entity_id, metadata, created_at)
            VALUES
                (:id, :action_type, :entity_type, :entity_id, :metadata, :created_at)
            """,
            {
                "id":          record.get("id"),
                "action_type": record.get("action_type"),
                "entity_type": record.get("entity_type"),
                "entity_id":   record.get("entity_id"),
                "metadata":    record.get("metadata"),
                "created_at":  record.get("created_at"),
            },
        )
        conn.commit()
    finally:
        db.close(conn)


def ingest(entity_type: str, payload: dict[str, Any], user_id: str) -> None:
    """
    Ingest a single entity into the user's storage.

    - Inserts/updates the row in the appropriate SQLite table.
    - If the entity type is searchable, also upserts into ChromaDB.

    Supported entity_types: goals, tasks, events, contacts,
                             behavior_patterns, goal_alignment.
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not entity_type:
        raise ValueError("entity_type is required")

    payload = _ensure_id(payload.copy())
    payload.setdefault("created_at", _now_iso())

    conn = db.get_connection(user_id)
    try:
        if entity_type == "goals":
            conn.execute(
                """
                INSERT OR IGNORE INTO goals (id, title, description, priority, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id"),
                    payload.get("title"),
                    payload.get("description"),
                    payload.get("priority"),
                    payload.get("created_at"),
                ),
            )
        elif entity_type == "tasks":
            conn.execute(
                """
                INSERT INTO tasks
                    (id, title, status, due_date, goal_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    status=excluded.status,
                    due_date=excluded.due_date
                """,
                (
                    payload.get("id"),
                    payload.get("title"),
                    payload.get("status"),
                    payload.get("due_date"),
                    payload.get("goal_id"),
                    payload.get("created_at"),
                ),
            )
        elif entity_type == "events":
            conn.execute(
                """
                INSERT OR IGNORE INTO events
                    (id, title, start_time, end_time, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id"),
                    payload.get("title"),
                    payload.get("start_time"),
                    payload.get("end_time"),
                    payload.get("created_at"),
                ),
            )
        elif entity_type == "contacts":
            conn.execute(
                """
                INSERT OR IGNORE INTO contacts
                    (id, name, email, last_interaction, importance_score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id"),
                    payload.get("name"),
                    payload.get("email"),
                    payload.get("last_interaction"),
                    payload.get("importance_score", 0.0),
                ),
            )
        elif entity_type == "behavior_patterns":
            conn.execute(
                """
                INSERT OR IGNORE INTO behavior_patterns
                    (id, pattern_type, description, confidence, last_updated)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id"),
                    payload.get("pattern_type"),
                    payload.get("description"),
                    payload.get("confidence"),
                    payload.get("last_updated"),
                ),
            )
        elif entity_type == "goal_alignment":
            conn.execute(
                """
                INSERT OR IGNORE INTO goal_alignment
                    (id, goal_id, entity_type, entity_id, alignment_score, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id"),
                    payload.get("goal_id"),
                    payload.get("entity_type"),
                    payload.get("entity_id"),
                    payload.get("alignment_score"),
                    payload.get("last_updated"),
                ),
            )
        else:
            raise ValueError(f"Unsupported entity_type: {entity_type!r}")

        conn.commit()
    finally:
        db.close(conn)

    # Embed searchable entities into ChromaDB
    if entity_type in _SEARCHABLE_ENTITY_TYPES:
        text = _text_for_embedding(entity_type, payload)
        vdb.add_document(
            user_id=user_id,
            entity_type=entity_type,
            doc_id=payload["id"],
            text=text,
            metadata={"entity_type": entity_type, "user_id": user_id},
        )


def create_task(user_id: str, payload: dict[str, Any]) -> dict:
    """
    Create a new task locally. Returns the created task as a dict.
    payload keys: title (required), due_date, goal_id, nudge_message
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not payload.get("title"):
        raise ValueError("title is required")

    record = _ensure_id(payload.copy())
    record.setdefault("status", "pending")
    record.setdefault("source", "local")
    now = _now_iso()
    record.setdefault("created_at", now)
    record["last_modified"] = now

    conn = db.get_connection(user_id)
    try:
        conn.execute(
            """
            INSERT INTO tasks (id, title, status, due_date, goal_id, nudge_message, nudge_time, nudge_enabled, last_modified, source, created_at)
            VALUES (:id, :title, :status, :due_date, :goal_id, :nudge_message, :nudge_time, :nudge_enabled, :last_modified, :source, :created_at)
            """,
            {
                "id":            record["id"],
                "title":         record.get("title"),
                "status":        record.get("status"),
                "due_date":      record.get("due_date"),
                "goal_id":       record.get("goal_id"),
                "nudge_message": record.get("nudge_message"),
                "nudge_time":    record.get("nudge_time"),
                "nudge_enabled": record.get("nudge_enabled", 1),
                "last_modified": record["last_modified"],
                "source":        record["source"],
                "created_at":    record["created_at"],
            },
        )
        conn.commit()
    finally:
        db.close(conn)

    return record


def update_task(user_id: str, task_id: str, updates: dict[str, Any]) -> dict | None:
    """
    Update an existing task. Only fields present in *updates* are changed.
    Allowed fields: title, status, due_date, goal_id, nudge_message.
    Returns the updated task row as a dict, or None if not found.
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not task_id:
        raise ValueError("task_id is required")

    allowed = {"title", "status", "due_date", "goal_id", "nudge_message", "nudge_time", "nudge_enabled", "nudge_times", "nudge_days"}
    fields  = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        raise ValueError("No valid update fields provided")

    fields["last_modified"] = _now_iso()
    fields["source"]        = "local"

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["_id"] = task_id

    conn = db.get_connection(user_id)
    try:
        conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = :_id",  # noqa: S608
            fields,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close(conn)


def delete_task(user_id: str, task_id: str) -> bool:
    """Delete a task. Returns True if a row was deleted, False if not found."""
    if not user_id:
        raise ValueError("user_id is required")
    conn = db.get_connection(user_id)
    try:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        db.close(conn)


def create_goal(user_id: str, payload: dict[str, Any]) -> dict:
    """
    Create a new goal locally. Returns the created goal as a dict.
    payload keys: title (required), description, priority
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not payload.get("title"):
        raise ValueError("title is required")

    record = _ensure_id(payload.copy())
    record.setdefault("source", "local")
    now = _now_iso()
    record.setdefault("created_at", now)
    record["last_modified"] = now

    conn = db.get_connection(user_id)
    try:
        conn.execute(
            """
            INSERT INTO goals (id, title, description, priority, last_modified, source, created_at)
            VALUES (:id, :title, :description, :priority, :last_modified, :source, :created_at)
            """,
            {
                "id":            record["id"],
                "title":         record.get("title"),
                "description":   record.get("description"),
                "priority":      record.get("priority", "medium"),
                "last_modified": record["last_modified"],
                "source":        record["source"],
                "created_at":    record["created_at"],
            },
        )
        conn.commit()
    finally:
        db.close(conn)

    return record


def update_goal(user_id: str, goal_id: str, updates: dict[str, Any]) -> dict | None:
    """
    Update an existing goal. Allowed fields: title, description, priority.
    Returns the updated row or None if not found.
    """
    if not user_id:
        raise ValueError("user_id is required")

    allowed = {"title", "description", "priority"}
    fields  = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        raise ValueError("No valid update fields provided")

    fields["last_modified"] = _now_iso()
    fields["source"]        = "local"
    fields["_id"]           = goal_id

    set_clause = ", ".join(f"{k} = :{k}" for k in fields if k != "_id")
    conn = db.get_connection(user_id)
    try:
        conn.execute(
            f"UPDATE goals SET {set_clause} WHERE id = :_id",  # noqa: S608
            fields,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close(conn)


def delete_goal(user_id: str, goal_id: str) -> bool:
    """
    Delete a goal and nullify goal_id on any tasks linked to it.
    Returns True if a goal row was deleted, False if not found.
    """
    if not user_id:
        raise ValueError("user_id is required")
    conn = db.get_connection(user_id)
    try:
        conn.execute("UPDATE tasks SET goal_id = NULL WHERE goal_id = ?", (goal_id,))
        cursor = conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        db.close(conn)


def get_tasks_due_for_nudge(user_id: str, hhmm: str, day_abbrev: str | None = None) -> list[dict]:
    """
    Return tasks due for a nudge at *hhmm* (HH:MM) that are enabled and not completed.

    Checks both legacy nudge_time (single HH:MM) and nudge_times (JSON array).
    If day_abbrev is provided (e.g. "mon"), only returns tasks whose nudge_days
    includes that day (or tasks with no nudge_days set, meaning every day).
    """
    if not user_id:
        raise ValueError("user_id is required")
    import json as _json
    conn = db.get_connection(user_id)
    try:
        rows = conn.execute(
            """
            SELECT * FROM tasks
            WHERE nudge_enabled = 1
              AND status != 'completed'
            """,
        ).fetchall()
        result = []
        for row in rows:
            task = dict(row)

            # Check if this time matches
            time_match = False
            nudge_times_raw = task.get("nudge_times")
            if nudge_times_raw:
                try:
                    times = _json.loads(nudge_times_raw)
                    time_match = hhmm in times
                except Exception:
                    pass
            if not time_match and task.get("nudge_time") == hhmm:
                time_match = True

            if not time_match:
                continue

            # Check if today's day is allowed
            if day_abbrev:
                nudge_days_raw = task.get("nudge_days")
                if nudge_days_raw:
                    try:
                        days = _json.loads(nudge_days_raw)
                        if days and day_abbrev not in days:
                            continue  # today not in allowed days
                    except Exception:
                        pass
                # if nudge_days is empty/null → every day → pass through

            result.append(task)
        return result
    finally:
        db.close(conn)


def list_tasks(
    user_id: str,
    status: str = "pending",
    limit: int = 50,
    goal_id: str | None = None,
) -> list[dict]:
    """Return tasks for user_id, optionally filtered by status and goal_id.

    status="all" returns every task regardless of status.
    """
    if not user_id:
        raise ValueError("user_id is required")
    conn = db.get_connection(user_id)
    try:
        where_parts: list[str] = []
        params: list[Any] = []

        if status != "all":
            where_parts.append("status = ?")
            params.append(status)

        if goal_id is not None:
            where_parts.append("goal_id = ?")
            params.append(goal_id)

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        params.append(limit)

        rows = conn.execute(
            f"SELECT * FROM tasks {where_sql} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close(conn)


def get_task(user_id: str, task_id: str) -> dict | None:
    """Fetch a single task by id. Returns None if not found."""
    if not user_id:
        raise ValueError("user_id is required")
    if not task_id:
        raise ValueError("task_id is required")
    conn = db.get_connection(user_id)
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close(conn)


def get_overdue_tasks(user_id: str) -> list[dict]:
    """Return all overdue tasks with nudge_message for the nudge engine."""
    if not user_id:
        raise ValueError("user_id is required")
    conn = db.get_connection(user_id)
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = 'overdue' ORDER BY due_date ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close(conn)


def get_preferences(user_id: str) -> dict:
    """Return the user's nudge preferences, creating defaults if not yet set."""
    if not user_id:
        raise ValueError("user_id is required")
    conn = db.get_connection(user_id)
    try:
        row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return dict(row)
        # Return defaults without inserting — insert happens on first save
        return {
            "user_id":           user_id,
            "morning_time":      "07:00",
            "midday_time":       "12:00",
            "evening_time":      "19:00",
            "max_nudges_per_day": 5,
            "min_gap_hours":     2.0,
            "strictness":        0.7,
        }
    finally:
        db.close(conn)


def save_preferences(user_id: str, updates: dict[str, Any]) -> dict:
    """Upsert nudge preferences for user_id. Only provided fields are changed."""
    if not user_id:
        raise ValueError("user_id is required")

    allowed = {"morning_time", "midday_time", "evening_time",
                "max_nudges_per_day", "min_gap_hours", "strictness"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        raise ValueError("No valid preference fields provided")

    conn = db.get_connection(user_id)
    try:
        # Upsert: insert defaults then update, or just update if exists
        conn.execute(
            """
            INSERT INTO user_preferences (user_id) VALUES (?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id,),
        )
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["user_id"]    = user_id
        fields["updated_at"] = _now_iso()
        conn.execute(
            f"UPDATE user_preferences SET {set_clause}, updated_at = :updated_at WHERE user_id = :user_id",  # noqa: S608
            fields,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row)
    finally:
        db.close(conn)


def save_push_subscription(user_id: str, subscription: dict) -> dict:
    """
    Store a Web Push subscription for user_id.
    subscription must contain: endpoint, keys.p256dh, keys.auth
    Upserts by endpoint — re-subscribing the same browser is idempotent.
    """
    if not user_id:
        raise ValueError("user_id is required")
    import json as _json
    endpoint = subscription.get("endpoint", "")
    if not endpoint:
        raise ValueError("endpoint is required")

    record = {
        "id":                str(uuid.uuid4()),
        "user_id":           user_id,
        "endpoint":          endpoint,
        "subscription_json": _json.dumps(subscription),
        "created_at":        _now_iso(),
    }
    conn = db.get_connection(user_id)
    try:
        conn.execute(
            """
            INSERT INTO push_subscriptions (id, user_id, endpoint, subscription_json, created_at)
            VALUES (:id, :user_id, :endpoint, :subscription_json, :created_at)
            ON CONFLICT(endpoint) DO UPDATE SET
                subscription_json = excluded.subscription_json,
                user_id = excluded.user_id
            """,
            record,
        )
        conn.commit()
    finally:
        db.close(conn)
    return record


def get_push_subscriptions(user_id: str) -> list[dict]:
    """Return all active Web Push subscriptions for user_id."""
    if not user_id:
        raise ValueError("user_id is required")
    import json as _json
    conn = db.get_connection(user_id)
    try:
        rows = conn.execute(
            "SELECT * FROM push_subscriptions WHERE user_id = ?", (user_id,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["subscription"] = _json.loads(d["subscription_json"])
            except Exception:
                d["subscription"] = {}
            result.append(d)
        return result
    finally:
        db.close(conn)


def delete_push_subscription(user_id: str, endpoint: str) -> bool:
    """Remove a push subscription (e.g. when browser unsubscribes)."""
    if not user_id:
        raise ValueError("user_id is required")
    conn = db.get_connection(user_id)
    try:
        cursor = conn.execute(
            "DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?",
            (user_id, endpoint),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        db.close(conn)


def semantic_search(user_id: str, query: str) -> list[dict]:
    """
    Perform semantic search over all of *user_id*'s embedded memory.

    Returns a list of result dicts ordered by relevance (closest first).
    Each dict contains: id, document, metadata, distance.
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not query:
        raise ValueError("query is required")

    return vdb.query_documents(user_id=user_id, query=query)
