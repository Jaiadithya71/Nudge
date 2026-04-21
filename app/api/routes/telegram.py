"""
api/routes/telegram.py — Telegram webhook endpoint.

Telegram calls POST /api/telegram/webhook when a user taps an inline button.
No JWT auth — Telegram is the caller. The endpoint is secured by obscurity
(URL not publicly advertised) for a personal single-user tool.

To register the webhook with Telegram:
    curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
         -H "Content-Type: application/json" \
         -d '{"url": "https://<your-ngrok-or-public-url>/api/telegram/webhook"}'

For local dev without ngrok, use long-polling instead (TELEGRAM_USE_POLLING=true).
"""

import logging
import os

from fastapi import APIRouter, Request

import api.dependencies  # noqa: F401 — ensures sys.path is patched
import notification_service as ns

router  = APIRouter()
logger  = logging.getLogger(__name__)
_USER_ID = os.environ.get("APP_USER_ID", "jai")


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Receives Telegram Update objects.
    Handles callback_query (inline button taps) → logs to user_actions via memory.
    """
    try:
        update = await request.json()
    except Exception:
        return {"ok": False, "error": "invalid JSON"}

    cq = update.get("callback_query")
    if not cq:
        # Ignore message updates, edited messages, etc.
        return {"ok": True}

    callback_query_id = cq.get("id", "")
    callback_data     = cq.get("data", "")
    msg               = cq.get("message", {})

    _TOAST = {"acknowledged": "✅ Acknowledged", "snoozed": "⏰ Snoozed", "ignored": "❌ Ignored"}

    action = ns.handle_callback(callback_data, _USER_ID)
    toast  = _TOAST.get(action, "Got it!")
    ns.answer_callback_query(callback_query_id, text=toast)

    if msg:
        ns.clear_message_buttons(msg["chat"]["id"], msg["message_id"], action)

    logger.info("[webhook] Telegram callback: action=%s user=%s", action, _USER_ID)
    return {"ok": True, "action": action}
