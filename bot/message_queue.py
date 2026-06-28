"""
Telegram ↔ Antigravity Message Queue Handler

File-based message queue for routing Telegram messages to Antigravity
and delivering responses back. Used by both cloud_bot.py (write inbox,
read outbox) and Antigravity (read inbox, write outbox).
"""

import json
import os
import uuid
import datetime
import threading

# Paths relative to bot/ directory
QUEUE_DIR = os.path.dirname(os.path.abspath(__file__))
INBOX_PATH = os.path.join(QUEUE_DIR, "telegram_inbox.json")
OUTBOX_PATH = os.path.join(QUEUE_DIR, "telegram_outbox.json")

_lock = threading.Lock()


def _read_json(path):
    """Read a JSON file, return empty list if missing or corrupt."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _write_json(path, data):
    """Write data to a JSON file atomically."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


# ── INBOX: Cloud Bot writes, Antigravity reads ──────────────────

def write_to_inbox(text: str) -> dict:
    """
    Cloud Bot calls this when a user sends a non-direct message.
    Returns the queued message dict.
    """
    msg = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "text": text,
        "status": "pending"
    }
    with _lock:
        inbox = _read_json(INBOX_PATH)
        inbox.append(msg)
        _write_json(INBOX_PATH, inbox)
    return msg


def read_pending_inbox() -> list:
    """
    Antigravity calls this to get unprocessed messages.
    Returns list of messages with status 'pending'.
    """
    inbox = _read_json(INBOX_PATH)
    return [m for m in inbox if m.get("status") == "pending"]


def mark_inbox_processed(msg_id: str):
    """Antigravity calls this after processing a message."""
    with _lock:
        inbox = _read_json(INBOX_PATH)
        for m in inbox:
            if m["id"] == msg_id:
                m["status"] = "processed"
                break
        _write_json(INBOX_PATH, inbox)


# ── OUTBOX: Antigravity writes, Cloud Bot reads ─────────────────

def write_to_outbox(msg_id: str, response: str):
    """
    Antigravity calls this to send a response back to the user.
    """
    entry = {
        "id": msg_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "response": response,
        "status": "ready"
    }
    with _lock:
        outbox = _read_json(OUTBOX_PATH)
        outbox.append(entry)
        _write_json(OUTBOX_PATH, outbox)


def read_ready_outbox() -> list:
    """
    Cloud Bot calls this to check for responses to send to Telegram.
    Returns list of messages with status 'ready'.
    """
    outbox = _read_json(OUTBOX_PATH)
    return [m for m in outbox if m.get("status") == "ready"]


def mark_outbox_delivered(msg_id: str):
    """Cloud Bot calls this after sending the response to Telegram."""
    with _lock:
        outbox = _read_json(OUTBOX_PATH)
        for m in outbox:
            if m["id"] == msg_id:
                m["status"] = "delivered"
                break
        _write_json(OUTBOX_PATH, outbox)


# ── HEALTH ───────────────────────────────────────────────────────

def get_antigravity_health() -> dict:
    """
    Check when Antigravity last wrote to the outbox.
    Returns health status and last activity time.
    """
    outbox = _read_json(OUTBOX_PATH)
    inbox = _read_json(INBOX_PATH)

    pending_count = len([m for m in inbox if m.get("status") == "pending"])

    if not outbox:
        return {
            "status": "unknown",
            "last_response": None,
            "pending_messages": pending_count
        }

    latest = max(outbox, key=lambda m: m.get("timestamp", ""))
    last_time = datetime.datetime.fromisoformat(latest["timestamp"].rstrip("Z"))
    age = datetime.datetime.utcnow() - last_time
    age_minutes = age.total_seconds() / 60

    return {
        "status": "active" if age_minutes < 15 else "possibly_down",
        "last_response": latest["timestamp"],
        "age_minutes": round(age_minutes, 1),
        "pending_messages": pending_count
    }


# ── CLEANUP ──────────────────────────────────────────────────────

def cleanup_old_messages(max_age_hours: int = 24):
    """Remove delivered/processed messages older than max_age_hours."""
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=max_age_hours)
    cutoff_str = cutoff.isoformat() + "Z"

    with _lock:
        inbox = _read_json(INBOX_PATH)
        inbox = [m for m in inbox if m.get("status") == "pending" or m.get("timestamp", "") > cutoff_str]
        _write_json(INBOX_PATH, inbox)

        outbox = _read_json(OUTBOX_PATH)
        outbox = [m for m in outbox if m.get("status") == "ready" or m.get("timestamp", "") > cutoff_str]
        _write_json(OUTBOX_PATH, outbox)
