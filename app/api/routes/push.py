"""
push.py — Web Push subscription management.

Endpoints:
    GET  /api/push/vapid-public-key  — returns the VAPID public key for the frontend
    POST /api/push/subscribe         — save a push subscription from the browser
    POST /api/push/unsubscribe       — remove a push subscription

Required env vars:
    VAPID_PUBLIC_KEY   — from generate_vapid_keys.py
    VAPID_PRIVATE_KEY  — from generate_vapid_keys.py
    VAPID_EMAIL        — mailto: address for the push server (e.g. mailto:you@example.com)
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user

import api.dependencies  # noqa — ensures sys.path patched
import memory as mem

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Push"])


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: dict  # p256dh, auth


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/push/vapid-public-key")
def get_vapid_public_key():
    """Return the VAPID public key so the frontend can subscribe."""
    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Web Push not configured (VAPID_PUBLIC_KEY missing)")
    return {"publicKey": key}


@router.post("/push/subscribe", status_code=201)
def subscribe(payload: SubscribeRequest, user_id: str = Depends(get_current_user)):
    """Save a browser push subscription."""
    subscription = {
        "endpoint": payload.endpoint,
        "keys":     payload.keys,
    }
    try:
        mem.save_push_subscription(user_id, subscription)
        logger.info("[push] Subscription saved: user=%s endpoint=%.60s", user_id, payload.endpoint)
        return {"status": "subscribed"}
    except Exception as e:
        logger.error("[push] Subscribe failed: user=%s error=%s", user_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/push/unsubscribe")
def unsubscribe(payload: UnsubscribeRequest, user_id: str = Depends(get_current_user)):
    """Remove a push subscription."""
    removed = mem.delete_push_subscription(user_id, payload.endpoint)
    logger.info("[push] Unsubscribed: user=%s found=%s", user_id, removed)
    return {"status": "unsubscribed"}


@router.post("/push/test")
def test_push(user_id: str = Depends(get_current_user)):
    """Send a test push notification to all subscriptions for this user."""
    import sys
    from pathlib import Path
    _root = str(Path(__file__).resolve().parent.parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from notification_service import send_web_push_nudge
    nudge = {
        "id":      "test-push",
        "type":    "Test",
        "message": "Push notifications are working!",
        "priority": "high",
    }
    subs = mem.get_push_subscriptions(user_id)
    if not subs:
        raise HTTPException(status_code=404, detail="No push subscriptions found. Enable notifications in the dashboard first.")
    ok = send_web_push_nudge(user_id, nudge)
    if ok:
        return {"status": "sent", "subscriptions": len(subs)}
    raise HTTPException(status_code=500, detail="Push send failed — check server logs for details.")
