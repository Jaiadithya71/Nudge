# WS4: Service Worker Notification Actions

> Priority: P1 — Important
> Dependencies: WS1 (unified notifications must be working)
> Estimated scope: 2 files changed

---

## Problem

When a push notification appears on Android, it shows "Done" and "Later" buttons (defined in `Dashboard/public/sw.js` line 25-28). But clicking them does nothing — the handler at line 37 has a `// Future:` comment and doesn't log the action to the backend.

This means:
- The user taps "Done" on a notification → nothing is recorded
- The nudge engine can't learn from user responses
- The evaluation endpoint (`/api/evaluation/today`) can't measure response rates for push notifications

---

## What To Do

### Change 1: Implement notification action handling in service worker

**File:** `Dashboard/public/sw.js`

Replace the `notificationclick` event listener with one that sends the action back to the server:

```javascript
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const nudgeId = event.notification.data?.nudge_id || "unknown";
  const action = event.action; // "ack" or "snooze", empty string if body clicked

  // Map service worker actions to backend action types
  const actionMap = {
    "ack": "acknowledged_nudge",
    "snooze": "snoozed_nudge",
  };

  const mappedAction = actionMap[action] || null;

  // Log the action to the backend if a button was pressed
  if (mappedAction) {
    const logPromise = fetch("http://localhost:8000/api/log-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: mappedAction,
        metadata: {
          nudge_id: nudgeId,
          source: "web_push",
        },
      }),
    }).catch(() => {
      // Silent fail — user may be offline
    });
    event.waitUntil(logPromise);
  }

  // Always open/focus the app
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow("/");
    })
  );
});
```

### Change 2: Make log-action work without auth for service worker calls

**Problem:** The `/api/log-action` endpoint requires a JWT bearer token. The service worker doesn't have access to localStorage (where the JWT is stored). This means the fetch call above will get a 401.

**File:** `api/routes/actions.py` (or wherever `log-action` is defined)

Check where `POST /api/log-action` is defined. There are two options:

**Option A (simpler, recommended):** Add a separate unauthenticated endpoint specifically for service worker action logging that uses a simple shared secret instead of JWT:

**File:** `api/main.py` — add a new route:

```python
@app.post("/api/sw-action")
async def sw_action(request: Request):
    """Log a nudge action from the service worker (no JWT required).
    Uses the nudge_id as proof of legitimacy — only someone who received the nudge has it."""
    body = await request.json()
    action = body.get("action", "")
    metadata = body.get("metadata", {})
    if not action or not metadata.get("nudge_id"):
        raise HTTPException(status_code=400, detail="action and metadata.nudge_id required")
    # Use the default user_id since this is a single-user system
    user_id = os.environ.get("APP_USER_ID", "jai")
    import memory as mem
    mem.log_action(user_id, {
        "action_type": action,
        "entity_type": "nudge",
        "entity_id": metadata.get("nudge_id", ""),
        "metadata": metadata,
    })
    return {"status": "logged"}
```

Then update the service worker fetch URL to use `/api/sw-action` instead of `/api/log-action`.

**Option B (if you prefer keeping one endpoint):** Store the JWT in the service worker via `postMessage` from the main app after login, and include it in the fetch headers. This is more complex and fragile.

**Recommendation: Use Option A.** This is a single-user system. The nudge_id serves as proof the user received the notification.

### Change 3: Make the backend URL configurable

**File:** `Dashboard/public/sw.js`

The hardcoded `http://localhost:8000` won't work in production. Since service workers can't read environment variables, use the service worker's own origin or pass the URL during registration:

For now (local dev only), hardcode is acceptable. Add a comment:
```javascript
// TODO: In production, read API_URL from a query param passed during SW registration
const API_BASE = "http://localhost:8000/api";
```

---

## What NOT To Do

- Do NOT change the notification display format (title, body, icon, badge)
- Do NOT add new action buttons beyond "Done" and "Later"
- Do NOT modify the push subscription flow in PushSetup.tsx
- Do NOT add offline queue logic — silent fail is acceptable for v1

---

## Files Touched

| File | Change |
|------|--------|
| `Dashboard/public/sw.js` | Implement action logging via fetch to backend |
| `api/main.py` | Add `POST /api/sw-action` unauthenticated endpoint |

---

## Acceptance Criteria

1. Receive a push notification (use `POST /api/push/test` to trigger)
2. Tap "Done" → server logs show: `[action] Logged: acknowledged_nudge, nudge_id=test-push, source=web_push`
3. Tap "Later" → server logs show: `[action] Logged: snoozed_nudge, nudge_id=..., source=web_push`
4. Tapping the notification body (not a button) → app opens, no action logged (this is correct)
5. `GET /api/evaluation/today` should count web_push actions in its response rate
6. If the server is unreachable when the user taps, the notification still dismisses (no error)
