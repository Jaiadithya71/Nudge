# WS1: Unified Notification Delivery

> Priority: P0 — Critical
> Dependencies: None
> Estimated scope: 3 files changed

---

## Problem

The system has two notification channels — Web Push (for Android PWA) and Telegram — but they aren't wired together. Right now:

- `Orchestrator/orchestrator.py` line 267: `_send_telegram(nudges)` only calls Telegram
- `Orchestrator/orchestrator.py` line 571: `_run_per_task_nudges()` also only calls `_send_telegram()`
- `notification_service.py` line 70: `send_notification()` already exists and calls BOTH web push and Telegram
- But nobody calls `send_notification()` — it's dead code

The web push infrastructure is fully built (VAPID keys, `push.py` routes, `PushSetup.tsx`, `sw.js`) but the pipeline never triggers it.

---

## What To Do

### Change 1: Replace `_send_telegram` with `send_notification` in orchestrator

**File:** `Orchestrator/orchestrator.py`

**Current** (line 267-274):
```python
def _send_telegram(nudges: list[dict]) -> None:
    """Best-effort Telegram delivery — failure never blocks the pipeline."""
    try:
        import notification_service as ns
        for nudge in nudges:
            ns.send_telegram_nudge(nudge)
    except Exception as exc:
        logger.warning("[telegram] Delivery skipped: %s", exc)
```

**Replace with:**
```python
def _send_notifications(user_id: str, nudges: list[dict]) -> None:
    """Best-effort notification delivery (Web Push + Telegram) — failure never blocks the pipeline."""
    try:
        import notification_service as ns
        for nudge in nudges:
            ns.send_notification(user_id, nudge)
    except Exception as exc:
        logger.warning("[notify] Delivery skipped: %s", exc)
```

**Then update all call sites:**

1. `run_job()` (line 528): Change `_send_telegram(nudges)` → `_send_notifications(user_id, nudges)`
2. `_run_per_task_nudges()` (line 571): Change `_send_telegram([nudge])` → `_send_notifications(user_id, [nudge])`

### Change 2: Ensure `send_notification` logs per-channel results

**File:** `notification_service.py`

The existing `send_notification()` (line 70) is already correct — it calls both `send_web_push_nudge()` and `send_telegram_nudge()`. But add a debug log so you can verify which channel succeeded:

```python
def send_notification(user_id: str, nudge: dict) -> bool:
    web_push_ok = send_web_push_nudge(user_id, nudge)
    telegram_ok = send_telegram_nudge(nudge)
    logger.info("[notify] user=%s web_push=%s telegram=%s nudge_type=%s",
                user_id, web_push_ok, telegram_ok, nudge.get("type"))
    return web_push_ok or telegram_ok
```

---

## What NOT To Do

- Do NOT change the `send_web_push_nudge()` or `send_telegram_nudge()` implementations
- Do NOT modify the push subscription routes in `api/routes/push.py`
- Do NOT change the service worker (`Dashboard/public/sw.js`)
- Do NOT add any new packages

---

## Files Touched

| File | Change |
|------|--------|
| `Orchestrator/orchestrator.py` | Rename `_send_telegram` → `_send_notifications`, add `user_id` param, update 2 call sites |
| `notification_service.py` | Add info log to `send_notification()` |

---

## Acceptance Criteria

1. Start the backend: `uvicorn api.main:app --reload`
2. Open dashboard, enable push notifications via the "Enable push notifications" button
3. Run `POST /api/push/test` via the API docs — should receive a push notification on the device
4. Create a task with `nudge_time` set to the current minute → within 60 seconds, the device should receive BOTH a Telegram message AND a Web Push notification
5. Server logs should show: `[notify] user=jai web_push=True telegram=True nudge_type=reminder`
6. If Telegram is not configured (no TELEGRAM_BOT_TOKEN), web push should still work independently
7. If no push subscriptions exist, Telegram should still work independently
