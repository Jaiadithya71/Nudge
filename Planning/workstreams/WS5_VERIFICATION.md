# WS5: End-to-End System Verification

> Priority: P0 — Final gate before daily use
> Dependencies: WS1, WS2, WS3, WS4 must all be complete
> Estimated scope: 1 new test file, manual test checklist

---

## Purpose

This workstream verifies the entire Nudge system works end-to-end as a daily-driver tool. It covers:
1. Automated API integration tests
2. Manual checklist for frontend + notifications
3. A simulated "day in the life" test scenario

---

## Part 1: Automated API Tests

**File:** `tests/test_full_system.py` (NEW)

Create a comprehensive test script that runs against a live server (`uvicorn api.main:app`). The script should use `requests` and follow the pattern of the existing `test_api.py`.

### Test Sequence

```python
"""
Full system verification — run against a live server.

Usage:
    1. Start server: uvicorn api.main:app --reload
    2. Run: python -X utf8 tests/test_full_system.py

Tests are ordered and must run sequentially (later tests depend on earlier state).
"""

import requests
import time
import json
import sys

BASE = "http://127.0.0.1:8000/api"
TOKEN = None
CREATED_TASK_IDS = []
CREATED_GOAL_IDS = []

def header():
    return {"Authorization": f"Bearer {TOKEN}"}

def test(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
    except AssertionError as e:
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")

# --- Auth ---

def test_login():
    global TOKEN
    # Uses APP_USER_ID and APP_PASSWORD from .env
    r = requests.post(f"{BASE}/auth/login", json={"user_id": "jai", "password": "<from .env>"})
    assert r.status_code == 200, f"Login failed: {r.status_code}"
    TOKEN = r.json()["access_token"]
    assert TOKEN, "No token returned"

def test_auth_me():
    r = requests.get(f"{BASE}/auth/me", headers=header())
    assert r.status_code == 200
    assert r.json()["user_id"] == "jai"

# --- Goals ---

def test_create_goal():
    r = requests.post(f"{BASE}/goals", json={
        "title": "Ship Nudge v1",
        "description": "Make the system usable as a daily driver",
        "priority": "high"
    }, headers=header())
    assert r.status_code == 201, f"Create goal failed: {r.text}"
    goal = r.json()
    CREATED_GOAL_IDS.append(goal["id"])
    assert goal["title"] == "Ship Nudge v1"

def test_update_goal():
    r = requests.patch(f"{BASE}/goals/{CREATED_GOAL_IDS[0]}", json={
        "description": "Updated description"
    }, headers=header())
    assert r.status_code == 200

def test_delete_goal():
    # Create a throwaway goal to delete
    r = requests.post(f"{BASE}/goals", json={"title": "Throwaway"}, headers=header())
    gid = r.json()["id"]
    r = requests.delete(f"{BASE}/goals/{gid}", headers=header())
    assert r.status_code == 204, f"Delete goal failed: {r.status_code}"

# --- Tasks ---

def test_create_task():
    r = requests.post(f"{BASE}/tasks", json={
        "title": "Renew insurance",
        "due_date": "2026-04-10",  # already past → should be overdue
        "goal_id": CREATED_GOAL_IDS[0],
        "nudge_message": "Stop procrastinating on insurance renewal.",
    }, headers=header())
    assert r.status_code == 201, f"Create task failed: {r.text}"
    task = r.json()
    CREATED_TASK_IDS.append(task["id"])
    assert task["title"] == "Renew insurance"

def test_create_task_with_nudge_config():
    r = requests.post(f"{BASE}/tasks", json={
        "title": "Write weekly report",
        "nudge_times": '["09:00","14:00"]',
        "nudge_days": '["mon","wed","fri"]',
        "nudge_message": "Report is due today. Write it now.",
    }, headers=header())
    assert r.status_code == 201
    CREATED_TASK_IDS.append(r.json()["id"])

def test_update_task_status():
    r = requests.patch(f"{BASE}/tasks/{CREATED_TASK_IDS[0]}", json={
        "status": "completed"
    }, headers=header())
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

def test_update_task_back_to_pending():
    r = requests.patch(f"{BASE}/tasks/{CREATED_TASK_IDS[0]}", json={
        "status": "pending"
    }, headers=header())
    assert r.status_code == 200

def test_delete_task():
    # Create a throwaway
    r = requests.post(f"{BASE}/tasks", json={"title": "Delete me"}, headers=header())
    tid = r.json()["id"]
    r = requests.delete(f"{BASE}/tasks/{tid}", headers=header())
    assert r.status_code == 204

# --- Context ---

def test_context_includes_tasks_and_goals():
    r = requests.get(f"{BASE}/context", headers=header())
    assert r.status_code == 200
    data = r.json()
    assert "tasks" in data
    assert "goals" in data
    assert "events" in data
    # Our created task should be in the list
    task_titles = [t["title"] for t in data["tasks"]]
    assert "Renew insurance" in task_titles, f"Created task not in context. Tasks: {task_titles}"

# --- Sync ---

def test_sync():
    r = requests.post(f"{BASE}/sync", json={}, headers=header())
    # May fail if Google credentials are expired — that's OK for this test
    assert r.status_code in (200, 500), f"Unexpected status: {r.status_code}"

# --- Insight ---

def test_insight():
    r = requests.get(f"{BASE}/insight", headers=header(), params={"mode": "mock"})
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "decision_signals" in data

# --- Nudges ---

def test_nudges():
    r = requests.get(f"{BASE}/nudges", headers=header(), params={"mode": "mock"})
    assert r.status_code == 200
    data = r.json()
    assert "nudges" in data

# --- Run Cycle ---

def test_run_morning_cycle():
    r = requests.post(f"{BASE}/run-cycle", json={
        "job_type": "morning", "mode": "mock"
    }, headers=header())
    assert r.status_code == 200

# --- Log Action ---

def test_log_action():
    r = requests.post(f"{BASE}/log-action", json={
        "action": "acknowledged_nudge",
        "metadata": {"nudge_id": "test-123", "source": "dashboard"}
    }, headers=header())
    assert r.status_code == 200

# --- SW Action (unauthenticated) ---

def test_sw_action():
    r = requests.post(f"{BASE}/sw-action", json={
        "action": "acknowledged_nudge",
        "metadata": {"nudge_id": "push-test-456", "source": "web_push"}
    })
    assert r.status_code == 200, f"SW action failed: {r.status_code} {r.text}"

# --- Preferences ---

def test_get_preferences():
    r = requests.get(f"{BASE}/preferences", headers=header())
    assert r.status_code == 200
    data = r.json()
    assert "max_nudges_per_day" in data

def test_update_preferences():
    r = requests.post(f"{BASE}/preferences", json={
        "strictness": 0.5
    }, headers=header())
    assert r.status_code == 200

# --- Evaluation ---

def test_evaluation():
    r = requests.get(f"{BASE}/evaluation/today", headers=header())
    assert r.status_code == 200

# --- Push ---

def test_vapid_key():
    r = requests.get(f"{BASE}/push/vapid-public-key", headers=header())
    # May be 503 if VAPID not configured — that's acceptable
    assert r.status_code in (200, 503)

# --- Cleanup ---

def test_cleanup():
    for tid in CREATED_TASK_IDS:
        requests.delete(f"{BASE}/tasks/{tid}", headers=header())
    for gid in CREATED_GOAL_IDS:
        requests.delete(f"{BASE}/goals/{gid}", headers=header())


# === Run all ===

if __name__ == "__main__":
    print("\n=== Nudge Full System Verification ===\n")

    print("Auth:")
    test("login", test_login)
    if not TOKEN:
        print("Cannot continue without auth. Check APP_USER_ID/APP_PASSWORD in .env")
        sys.exit(1)
    test("auth/me", test_auth_me)

    print("\nGoals:")
    test("create goal", test_create_goal)
    test("update goal", test_update_goal)
    test("delete goal", test_delete_goal)

    print("\nTasks:")
    test("create task", test_create_task)
    test("create task with nudge config", test_create_task_with_nudge_config)
    test("update task status", test_update_task_status)
    test("update task back to pending", test_update_task_back_to_pending)
    test("delete task", test_delete_task)

    print("\nContext:")
    test("context includes tasks and goals", test_context_includes_tasks_and_goals)

    print("\nSync:")
    test("sync", test_sync)

    print("\nPipeline:")
    test("insight", test_insight)
    test("nudges", test_nudges)
    test("run morning cycle", test_run_morning_cycle)

    print("\nActions:")
    test("log action", test_log_action)
    test("sw action (unauthenticated)", test_sw_action)

    print("\nPreferences:")
    test("get preferences", test_get_preferences)
    test("update preferences", test_update_preferences)

    print("\nEvaluation:")
    test("evaluation", test_evaluation)

    print("\nPush:")
    test("vapid key", test_vapid_key)

    print("\nCleanup:")
    test("cleanup", test_cleanup)

    print("\n=== Done ===\n")
```

**Important:** The agent implementing this test must replace `"<from .env>"` with the actual password read from `.env`, or better yet, read it from the `.env` file at runtime using `python-dotenv`.

---

## Part 2: Manual Frontend Checklist

Run through this checklist with the server + dashboard running:

### Login & Navigation
- [ ] Open http://localhost:3000 → redirected to /login
- [ ] Login with credentials → dashboard loads
- [ ] Sync button works (no error)
- [ ] Sign out → returns to login

### Tasks
- [ ] Quick-add a task → appears in "Pending" list
- [ ] Tap task → expands to show due date, nudge config, goal selector
- [ ] Set due date to yesterday → save → task moves to "Overdue" group (after context refresh)
- [ ] Set nudge times (e.g., 8am + 3pm) → save → shows "8 am, 3 pm" under task title
- [ ] Set nudge days (Mon, Wed, Fri) → save → shows "Mon, Wed, Fri" under task title
- [ ] Write custom nudge message → save
- [ ] Toggle "Notifications off" → save → shows "silent" label
- [ ] Complete task (circle button) → moves to "Done" group
- [ ] Uncomplete task → moves back to "Pending"
- [ ] Delete task (X button) → confirmation dialog → task removed
- [ ] Link task to a goal via dropdown → save

### Goals
- [ ] Quick-add a goal → appears in goal list
- [ ] Expand goal → edit title, description, priority
- [ ] Delete goal → confirmation → removed
- [ ] Goal shows count of linked tasks
- [ ] Delete a goal that has linked tasks → tasks' goal_id becomes null

### Nudges
- [ ] Nudge section shows nudges (may need to run a cycle first)
- [ ] Nudge messages reference actual task names (not generic)
- [ ] Acknowledge/snooze/ignore buttons work
- [ ] Nudge disappears after action

### Notifications
- [ ] "Enable push notifications" button → browser permission prompt
- [ ] After enabling, `POST /api/push/test` → notification appears on device
- [ ] Notification shows "Done" and "Later" buttons
- [ ] Tapping "Done" → action logged in server (check logs)
- [ ] Tapping "Later" → action logged
- [ ] Create task with nudge_time = current minute → notification fires within 60s

### Settings
- [ ] Open settings panel (gear icon)
- [ ] Change morning/midday/evening times → save
- [ ] Change max nudges per day → save
- [ ] Change strictness → save
- [ ] Close settings panel

### Insight
- [ ] Insight section shows AI summary
- [ ] If using mock mode, shows deterministic mock insight

---

## Part 3: "Day in the Life" Scenario

This is a scripted walkthrough to verify the system works as a coherent product.

### Setup
1. Start backend: `uvicorn api.main:app --reload`
2. Start frontend: `cd Dashboard && npm run dev`
3. Login to dashboard

### Morning (simulate)
1. Add 3 tasks: "Review PR", "Write blog post", "Call dentist"
2. Set "Call dentist" due date to yesterday
3. Set custom nudge message on "Call dentist": "You've been putting this off for weeks."
4. Set nudge times on "Review PR": 9am, 2pm
5. Create a goal: "Ship product this week" (high priority)
6. Link "Review PR" and "Write blog post" to the goal
7. Run morning cycle: `POST /api/run-cycle {"job_type": "morning", "mode": "mock"}`
8. Check: nudge appears referencing "Call dentist" by name
9. Check: insight section shows summary

### Midday (simulate)
10. Run midday cycle: `POST /api/run-cycle {"job_type": "midday", "mode": "mock"}`
11. Check: activation nudge mentions pending task count

### Activity
12. Complete "Review PR" (click the circle)
13. Acknowledge the nudge about "Call dentist"
14. Check: task moves to "Done" group

### Evening (simulate)
15. Run evening cycle: `POST /api/run-cycle {"job_type": "evening", "mode": "mock"}`
16. Check: reflection nudge appears

### Verification
17. `GET /api/evaluation/today` → should show nudges sent, at least 1 acknowledged
18. Check that no more than `max_nudges_per_day` nudges were delivered total

---

## What NOT To Do

- Do NOT modify any source code in this workstream — only create test files
- Do NOT add testing frameworks (no pytest, jest) — use plain requests + assertions
- Do NOT create mock servers or fixtures — test against the real running system

---

## Files Created

| File | Purpose |
|------|--------|
| `tests/test_full_system.py` | Automated API integration tests |

---

## Acceptance Criteria

1. `python -X utf8 tests/test_full_system.py` passes all tests against a running server
2. All manual checklist items pass
3. "Day in the life" scenario completes without errors
4. Server logs show both web_push and telegram delivery attempts
5. No Python tracebacks in server output during any test
