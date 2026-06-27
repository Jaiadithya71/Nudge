"""
db.py — SQLite connection + initialisation for the Memory module.

Each user gets an isolated database at:
    data/{user_id}/mirror.db

Schema is applied from schema.sql on first connection. The module is
intentionally thin — just connection management and raw helpers.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# Locate schema.sql relative to this file
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _data_dir(user_id: str) -> Path:
    """Return (and create) the per-user data directory."""
    root = os.environ.get("NUDGE_DATA_DIR") or str(Path(__file__).parent / "data")
    base = Path(root) / user_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_connection(user_id: str) -> sqlite3.Connection:
    """
    Return a sqlite3 connection for *user_id*.

    - Enables WAL mode for better concurrent reads.
    - Enforces foreign keys.
    - Returns rows as sqlite3.Row for dict-like access.
    - Applies schema.sql on the very first connection (tables use IF NOT EXISTS).
    """
    db_path = _data_dir(user_id) / "mirror.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    # Apply schema — all statements are idempotent (CREATE TABLE IF NOT EXISTS)
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    # Strip the markdown header line that lives at the top of schema.sql
    statements = [
        s.strip()
        for s in schema_sql.split(";")
        if s.strip() and not s.strip().startswith("#")
    ]
    for stmt in statements:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            # Indexes may throw if they already exist on older SQLite versions
            pass
    conn.commit()
    migrate(conn)
    return conn


def close(conn: sqlite3.Connection) -> None:
    """Safely close a connection."""
    try:
        conn.close()
    except Exception:
        pass


def migrate(conn: sqlite3.Connection) -> None:
    """
    Apply additive migrations to an existing DB.
    Each ALTER TABLE is wrapped in try/except — SQLite raises if the column
    already exists, which is the normal case after the first run.
    """
    migrations = [
        "ALTER TABLE tasks ADD COLUMN nudge_message TEXT",
        "ALTER TABLE tasks ADD COLUMN nudge_time TEXT",
        "ALTER TABLE tasks ADD COLUMN nudge_enabled INTEGER DEFAULT 1",
        "ALTER TABLE tasks ADD COLUMN last_modified TIMESTAMP",
        "ALTER TABLE tasks ADD COLUMN source TEXT DEFAULT 'notion'",
        "ALTER TABLE goals ADD COLUMN last_modified TIMESTAMP",
        "ALTER TABLE goals ADD COLUMN source TEXT DEFAULT 'notion'",
        """CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            morning_time TEXT DEFAULT '07:00',
            midday_time  TEXT DEFAULT '12:00',
            evening_time TEXT DEFAULT '19:00',
            max_nudges_per_day INTEGER DEFAULT 5,
            min_gap_hours REAL DEFAULT 2.0,
            strictness REAL DEFAULT 0.7,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE tasks ADD COLUMN nudge_times TEXT",
        "ALTER TABLE tasks ADD COLUMN nudge_days TEXT",
        """CREATE TABLE IF NOT EXISTS push_subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            subscription_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
