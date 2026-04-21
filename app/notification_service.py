"""
notification_service.py — Proactive nudge delivery.

Primary channel:  Web Push (Android PWA — no third-party dependency)
Fallback channel: Telegram (retained for when the app is not open)

Web Push required env vars:
    VAPID_PUBLIC_KEY   — from generate_vapid_keys.py
    VAPID_PRIVATE_KEY  — from generate_vapid_keys.py
    VAPID_EMAIL        — mailto: address (e.g. mailto:you@example.com)

Telegram env vars (fallback, optional):
    TELEGRAM_BOT_TOKEN  — from BotFather
    TELEGRAM_CHAT_ID    — your personal chat ID with the bot
    TELEGRAM_USE_POLLING=true  — enables long-polling thread (default for local dev)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_NUDGE_ROOT = Path(__file__).resolve().parent
_TAPI = "https://api.telegram.org/bot{token}/{method}"

# Priority → emoji
_PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def _chat_id() -> str | None:
    return os.environ.get("TELEGRAM_CHAT_ID")


def _call(method: str, payload: dict) -> dict:
    token = _token()
    if not token:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN not set")
    url = _TAPI.format(token=token, method=method)
    resp = requests.post(url, json=payload, timeout=8)
    resp.raise_for_status()
    return resp.json()


def _ensure_memory_on_path() -> None:
    """Make Memory and Orchestrator importable from notification_service context."""
    for sub in ("Memory", "Orchestrator"):
        p = str(_NUDGE_ROOT / sub)
        if p not in sys.path:
            sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Public: unified send — Web Push first, Telegram fallback
# ---------------------------------------------------------------------------

def send_notification(user_id: str, nudge: dict) -> bool:
    """
    Send a nudge via Web Push (primary) with Telegram as fallback.
    Returns True if at least one channel succeeded.
    """
    web_push_ok = send_web_push_nudge(user_id, nudge)
    telegram_ok = send_telegram_nudge(nudge)
    logger.info("[notify] user=%s web_push=%s telegram=%s nudge_type=%s",
                user_id, web_push_ok, telegram_ok, nudge.get("type"))
    return web_push_ok or telegram_ok


# ---------------------------------------------------------------------------
# Web Push delivery
# ---------------------------------------------------------------------------

def send_web_push_nudge(user_id: str, nudge: dict) -> bool:
    """
    Send a nudge to all stored Web Push subscriptions for user_id.
    Returns True if at least one subscription received the push.
    Requires: pip install pywebpush
    """
    import json as _json

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_email   = os.environ.get("VAPID_EMAIL", "")

    if not vapid_private or not vapid_email:
        logger.debug("[push] VAPID not configured — skipping web push.")
        return False

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("[push] pywebpush not installed. Run: pip install pywebpush")
        return False

    _ensure_memory_on_path()
    try:
        import memory as mem
        subscriptions = mem.get_push_subscriptions(user_id)
    except Exception as e:
        logger.warning("[push] Could not load subscriptions: %s", e)
        return False

    if not subscriptions:
        logger.debug("[push] No push subscriptions for user=%s", user_id)
        return False

    title   = nudge.get("type", "Nudge").upper()
    body    = nudge.get("message", "")
    payload = _json.dumps({"title": title, "body": body, "nudge_id": nudge.get("id", "")})

    success = False
    for sub in subscriptions:
        subscription_info = sub.get("subscription", {})
        if not subscription_info.get("endpoint"):
            continue
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_email},
            )
            logger.info("[push] Sent to endpoint=%.60s user=%s", subscription_info["endpoint"], user_id)
            success = True
        except WebPushException as e:
            if e.response is not None and e.response.status_code == 410:
                # Subscription expired — clean it up
                try:
                    mem.delete_push_subscription(user_id, subscription_info["endpoint"])
                    logger.info("[push] Removed expired subscription for user=%s", user_id)
                except Exception:
                    pass
            else:
                logger.warning("[push] WebPushException: %s", e)
        except Exception as e:
            logger.warning("[push] Push failed: %s", e)

    return success


# ---------------------------------------------------------------------------
# Public: send nudge (Telegram)
# ---------------------------------------------------------------------------

def send_telegram_nudge(nudge: dict) -> bool:
    """
    Send a nudge to the configured Telegram chat with inline action buttons.
    Returns True on success, False on failure — never raises.

    nudge dict must contain: id, type, message, priority.
    """
    token = _token()
    chat_id = _chat_id()
    if not token or not chat_id:
        logger.debug("[telegram] Not configured — skipping delivery.")
        return False

    nudge_id   = nudge.get("id", "unknown")
    nudge_type = nudge.get("type", "nudge")
    priority   = nudge.get("priority", "medium")
    message    = nudge.get("message", "")

    emoji = _PRIORITY_EMOJI.get(priority, "⚪")
    text  = f"{emoji} *{nudge_type.upper()}*\n\n{message}"

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Acknowledge", "callback_data": f"ack:{nudge_id}"},
            {"text": "⏰ Snooze",      "callback_data": f"snooze:{nudge_id}"},
            {"text": "❌ Ignore",      "callback_data": f"ignore:{nudge_id}"},
        ]]
    }

    try:
        _call("sendMessage", {
            "chat_id":      chat_id,
            "text":         text,
            "parse_mode":   "Markdown",
            "reply_markup": keyboard,
        })
        logger.info("[telegram] Sent: type=%s id=%s", nudge_type, nudge_id)
        return True
    except Exception as exc:
        logger.warning("[telegram] Send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public: handle callback from inline buttons
# ---------------------------------------------------------------------------

_ACTION_MAP = {"ack": "acknowledged", "snooze": "snoozed", "ignore": "ignored"}


def handle_callback(callback_data: str, user_id: str) -> str:
    """
    Parse a Telegram callback_data string and log the user action.

    callback_data format: "{raw_action}:{nudge_id}"
    e.g. "ack:550e8400-e29b-41d4-a716-446655440000"

    Returns the mapped action string.
    """
    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        logger.warning("[telegram] Unexpected callback_data: %r", callback_data)
        return "unknown"

    raw_action, nudge_id = parts
    action = _ACTION_MAP.get(raw_action, raw_action)

    try:
        _ensure_memory_on_path()
        import memory as mem
        mem.log_action(user_id, {
            "action_type": action,
            "entity_type": "nudge",
            "entity_id":   nudge_id,
            "metadata":    {"source": "telegram", "nudge_id": nudge_id},
        })
        logger.info("[telegram] Logged: action=%s nudge_id=%s user=%s", action, nudge_id, user_id)
    except Exception as exc:
        logger.warning("[telegram] Failed to log action: %s", exc)

    return action


def answer_callback_query(callback_query_id: str, text: str = "Got it!") -> None:
    """Dismiss the loading spinner on the Telegram button."""
    try:
        _call("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": text,
        })
    except Exception as exc:
        logger.debug("[telegram] answerCallbackQuery failed: %s", exc)


def clear_message_buttons(chat_id: str | int, message_id: int, action: str) -> None:
    """
    Remove inline buttons after the user responds — prevents double-tap.
    Uses editMessageReplyMarkup to wipe the keyboard in place.
    The action confirmation is shown as the answerCallbackQuery toast.
    """
    try:
        _call("editMessageReplyMarkup", {
            "chat_id":      chat_id,
            "message_id":   message_id,
            "reply_markup": {"inline_keyboard": []},
        })
        logger.debug("[telegram] Buttons cleared for message_id=%s", message_id)
    except Exception as exc:
        logger.debug("[telegram] clearButtons failed: %s", exc)


# ---------------------------------------------------------------------------
# Public: long-polling loop (local dev, no ngrok needed)
# ---------------------------------------------------------------------------

def start_polling(user_id: str) -> None:
    """
    Blocking long-polling loop. Run in a daemon thread.
    Receives callback_query updates from Telegram every 30 s.
    Does NOT require a public URL — works on localhost.
    """
    import time

    token = _token()
    if not token:
        logger.warning("[telegram] Polling not started — TELEGRAM_BOT_TOKEN not set.")
        return

    url    = f"https://api.telegram.org/bot{token}/getUpdates"
    offset = 0

    _TOAST = {"acknowledged": "✅ Acknowledged", "snoozed": "⏰ Snoozed", "ignored": "❌ Ignored"}

    logger.info("[telegram] Long-polling started for user=%s", user_id)
    while True:
        try:
            resp = requests.get(
                url,
                params={
                    "offset":          offset,
                    "timeout":         30,
                    "allowed_updates": ["callback_query"],
                },
                timeout=35,
            )
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                cq = update.get("callback_query")
                if cq:
                    action = handle_callback(cq.get("data", ""), user_id)
                    toast  = _TOAST.get(action, "Got it!")
                    answer_callback_query(cq["id"], text=toast)
                    msg = cq.get("message", {})
                    if msg:
                        clear_message_buttons(msg["chat"]["id"], msg["message_id"], action)
        except Exception as exc:
            logger.debug("[telegram] Polling error: %s", exc)
            time.sleep(5)
