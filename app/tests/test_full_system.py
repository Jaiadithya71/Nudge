"""
Full system verification — run against a live server.

Usage:
    1. Start server: uvicorn api.main:app --reload
    2. Run: python -X utf8 tests/test_full_system.py

Tests are ordered and must run sequentially (later tests depend on earlier state).
Credentials are read from .env (APP_USER_ID, APP_PASSWORD).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Load credentials from .env
# ---------------------------------------------------------------------------

def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

_load_env()

BASE          = "http://127.0.0.1:8000/api"
USER_ID       = os.environ.get("APP_USER_ID", "jai")
PASSWORD      = os.environ.get("APP_PASSWORD", "nudge-admin-password")
TOKEN: str | None = None

CREATED_TASK_IDS: list[str] = []
CREATED_GOAL_IDS: list[str] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _header() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


_PASS = 0
_FAIL = 0

def _run(name: str, fn) -> None:
    global _PASS, _FAIL
    try:
        fn()
        print(f"  [PASS] {name}")
        _PASS += 1
    except AssertionError as e:
        print(f"  [FAIL] {name}: {e}")
        _FAIL += 1
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        _FAIL += 1


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_login():
    global TOKEN
    r = requests.post(f"{BASE}/auth/login", json={"user_id": USER_ID, "password": PASSWORD}, timeout=10)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    TOKEN = r.json()["access_token"]
    assert TOKEN, "No token returned"


def test_auth_me():
    r = requests.get(f"{BASE}/auth/me", headers=_header(), timeout=10)
    assert r.status_code == 200, f"Got {r.status_code}"
    assert r.json()["user_id"] == USER_ID


# ---------------------------------------------------------------------------
# Goals CRUD
# ---------------------------------------------------------------------------

def test_create_goal():
    r = requests.post(f"{BASE}/goals", json={
        "title": "Ship Nudge v1",
        "description": "Make the system usable as a daily driver",
        "priority": "high",
    }, headers=_header(), timeout=10)
    assert r.status_code == 201, f"Create goal failed: {r.status_code} {r.text}"
    goal = r.json()
    CREATED_GOAL_IDS.append(goal["id"])
    assert goal["title"] == "Ship Nudge v1"
    assert goal["priority"] == "high"


def test_update_goal():
    gid = CREATED_GOAL_IDS[0]
    r = requests.patch(f"{BASE}/goals/{gid}", json={
        "description": "Updated description via WS5 test",
    }, headers=_header(), timeout=10)
    assert r.status_code == 200, f"Update goal failed: {r.status_code} {r.text}"
    assert r.json()["description"] == "Updated description via WS5 test"


def test_delete_goal_throwaway():
    r = requests.post(f"{BASE}/goals", json={"title": "Throwaway goal"}, headers=_header(), timeout=10)
    assert r.status_code == 201
    gid = r.json()["id"]
    r = requests.delete(f"{BASE}/goals/{gid}", headers=_header(), timeout=10)
    assert r.status_code == 204, f"Delete goal failed: {r.status_code} {r.text}"


def test_delete_goal_404():
    r = requests.delete(f"{BASE}/goals/nonexistent-goal-id", headers=_header(), timeout=10)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ---------------------------------------------------------------------------
# Tasks CRUD
# ---------------------------------------------------------------------------

def test_create_task_linked_to_goal():
    r = requests.post(f"{BASE}/tasks", json={
        "title": "Renew insurance",
        "due_date": "2026-01-01",
        "goal_id": CREATED_GOAL_IDS[0],
        "nudge_message": "Stop procrastinating on insurance renewal.",
    }, headers=_header(), timeout=10)
    assert r.status_code == 201, f"Create task failed: {r.status_code} {r.text}"
    task = r.json()
    CREATED_TASK_IDS.append(task["id"])
    assert task["title"] == "Renew insurance"
    assert task["goal_id"] == CREATED_GOAL_IDS[0]


def test_create_task_with_nudge_config():
    r = requests.post(f"{BASE}/tasks", json={
        "title": "Write weekly report",
        "nudge_times": '["09:00","14:00"]',
        "nudge_days": '["mon","wed","fri"]',
        "nudge_message": "Report is due today. Write it now.",
        "nudge_enabled": 1,
    }, headers=_header(), timeout=10)
    assert r.status_code == 201, f"Create task failed: {r.status_code} {r.text}"
    task = r.json()
    CREATED_TASK_IDS.append(task["id"])
    assert task["nudge_message"] == "Report is due today. Write it now."


def test_update_task_status_to_completed():
    tid = CREATED_TASK_IDS[0]
    r = requests.patch(f"{BASE}/tasks/{tid}", json={"status": "completed"}, headers=_header(), timeout=10)
    assert r.status_code == 200, f"Update task failed: {r.status_code}"
    assert r.json()["status"] == "completed"


def test_update_task_status_back_to_pending():
    tid = CREATED_TASK_IDS[0]
    r = requests.patch(f"{BASE}/tasks/{tid}", json={"status": "pending"}, headers=_header(), timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_update_task_goal_link():
    tid = CREATED_TASK_IDS[1]
    r = requests.patch(f"{BASE}/tasks/{tid}", json={
        "goal_id": CREATED_GOAL_IDS[0],
    }, headers=_header(), timeout=10)
    assert r.status_code == 200
    assert r.json()["goal_id"] == CREATED_GOAL_IDS[0]


def test_delete_task_throwaway():
    r = requests.post(f"{BASE}/tasks", json={"title": "Delete me"}, headers=_header(), timeout=10)
    assert r.status_code == 201
    tid = r.json()["id"]
    r = requests.delete(f"{BASE}/tasks/{tid}", headers=_header(), timeout=10)
    assert r.status_code == 204, f"Delete task failed: {r.status_code}"


def test_delete_task_404():
    r = requests.delete(f"{BASE}/tasks/nonexistent-task-id", headers=_header(), timeout=10)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ---------------------------------------------------------------------------
# Context — verify tasks and goals appear
# ---------------------------------------------------------------------------

def test_context_contains_created_data():
    r = requests.get(f"{BASE}/context", headers=_header(), timeout=10)
    assert r.status_code == 200, f"Context failed: {r.status_code}"
    data = r.json()
    assert "tasks" in data and "goals" in data and "events" in data

    task_titles = [t["title"] for t in data["tasks"]]
    assert "Renew insurance" in task_titles, f"Created task missing from context. Tasks: {task_titles}"

    goal_titles = [g["title"] for g in data["goals"]]
    assert "Ship Nudge v1" in goal_titles, f"Created goal missing from context. Goals: {goal_titles}"


def test_goal_deletion_nullifies_task_goal_id():
    """Create a goal, link a task, delete the goal — task's goal_id must become null."""
    # Create goal
    rg = requests.post(f"{BASE}/goals", json={"title": "Temp goal for nullify test"}, headers=_header(), timeout=10)
    assert rg.status_code == 201
    gid = rg.json()["id"]

    # Create task linked to it
    rt = requests.post(f"{BASE}/tasks", json={"title": "Task linked to temp goal", "goal_id": gid}, headers=_header(), timeout=10)
    assert rt.status_code == 201
    tid = rt.json()["id"]
    CREATED_TASK_IDS.append(tid)

    # Delete the goal
    rd = requests.delete(f"{BASE}/goals/{gid}", headers=_header(), timeout=10)
    assert rd.status_code == 204

    # Verify the task's goal_id is now null via context
    ctx = requests.get(f"{BASE}/context", headers=_header(), timeout=10).json()
    matching = [t for t in ctx["tasks"] if t["id"] == tid]
    assert matching, "Task not found in context after goal deletion"
    assert matching[0]["goal_id"] is None, f"goal_id not nullified: {matching[0]['goal_id']}"


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def test_sync():
    r = requests.post(f"{BASE}/sync", json={}, headers=_header(), timeout=30)
    # Google credentials may be expired — 500 is acceptable; 200 is ideal
    assert r.status_code in (200, 500), f"Unexpected sync status: {r.status_code}"


# ---------------------------------------------------------------------------
# Pipeline: Insight + Nudges + Run Cycle
# ---------------------------------------------------------------------------

def test_insight_mock():
    r = requests.get(f"{BASE}/insight", headers=_header(), params={"mode": "mock"}, timeout=15)
    assert r.status_code == 200, f"Insight failed: {r.status_code}"
    data = r.json()
    assert "summary" in data, "No summary in insight"
    assert "decision_signals" in data, "No decision_signals in insight"
    ds = data["decision_signals"]
    for flag in ("needs_activation", "needs_correction", "goal_at_risk", "has_overdue_tasks"):
        assert isinstance(ds.get(flag), bool), f"decision_signals.{flag} is not bool"


def test_nudges_mock():
    r = requests.get(f"{BASE}/nudges", headers=_header(), params={"mode": "mock"}, timeout=15)
    assert r.status_code == 200, f"Nudges failed: {r.status_code}"
    data = r.json()
    assert "nudges" in data
    for n in data["nudges"]:
        for field in ("type", "message", "priority", "timing"):
            assert field in n, f"Nudge missing field: {field}"


def test_run_morning_cycle():
    r = requests.post(f"{BASE}/run-cycle", json={"job_type": "morning", "mode": "mock"}, headers=_header(), timeout=30)
    assert r.status_code == 200, f"Run cycle failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("status") == "success", f"Cycle status not success: {body}"
    assert isinstance(body.get("nudges_generated"), int)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def test_log_action():
    r = requests.post(f"{BASE}/log-action", json={
        "action": "acknowledged_nudge",
        "metadata": {"nudge_id": "test-ws5-123", "source": "dashboard"},
    }, headers=_header(), timeout=10)
    assert r.status_code == 200, f"Log action failed: {r.status_code}"
    assert r.json().get("status") == "success"


def test_sw_action_unauthenticated():
    """Service worker action endpoint is intentionally unauthenticated."""
    r = requests.post(f"{BASE}/sw-action", json={
        "action": "acknowledged_nudge",
        "metadata": {"nudge_id": "push-test-ws5-456", "source": "web_push"},
    }, timeout=10)
    assert r.status_code == 200, f"SW action failed: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def test_get_preferences():
    r = requests.get(f"{BASE}/preferences", headers=_header(), timeout=10)
    assert r.status_code == 200, f"Get preferences failed: {r.status_code}"
    data = r.json()
    for field in ("max_nudges_per_day", "min_gap_hours", "strictness"):
        assert field in data, f"Preferences missing field: {field}"


def test_update_preferences():
    r = requests.post(f"{BASE}/preferences", json={"strictness": 0.6}, headers=_header(), timeout=10)
    assert r.status_code == 200, f"Update preferences failed: {r.status_code}"
    assert r.json()["strictness"] == 0.6


def test_restore_preferences():
    r = requests.post(f"{BASE}/preferences", json={"strictness": 0.7}, headers=_header(), timeout=10)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def test_evaluation_today():
    r = requests.get(f"{BASE}/evaluation/today", headers=_header(), timeout=10)
    assert r.status_code == 200, f"Evaluation failed: {r.status_code}"


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------

def test_vapid_public_key():
    r = requests.get(f"{BASE}/push/vapid-public-key", headers=_header(), timeout=10)
    # 503 is acceptable when VAPID is not configured
    assert r.status_code in (200, 503), f"Unexpected vapid status: {r.status_code}"
    if r.status_code == 200:
        assert "publicKey" in r.json(), "Missing publicKey in response"


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def test_cleanup():
    for tid in CREATED_TASK_IDS:
        requests.delete(f"{BASE}/tasks/{tid}", headers=_header(), timeout=10)
    for gid in CREATED_GOAL_IDS:
        requests.delete(f"{BASE}/goals/{gid}", headers=_header(), timeout=10)
    # No assertion — best-effort cleanup


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_ALL_TESTS: list[tuple[str, list]] = [
    ("Auth", [
        ("login",    test_login),
        ("auth/me",  test_auth_me),
    ]),
    ("Goals", [
        ("create goal",                     test_create_goal),
        ("update goal",                     test_update_goal),
        ("delete goal (throwaway)",         test_delete_goal_throwaway),
        ("delete goal -> 404",              test_delete_goal_404),
    ]),
    ("Tasks", [
        ("create task linked to goal",      test_create_task_linked_to_goal),
        ("create task with nudge config",   test_create_task_with_nudge_config),
        ("update task -> completed",        test_update_task_status_to_completed),
        ("update task -> pending",          test_update_task_status_back_to_pending),
        ("update task goal link",           test_update_task_goal_link),
        ("delete task (throwaway)",         test_delete_task_throwaway),
        ("delete task -> 404",              test_delete_task_404),
    ]),
    ("Context", [
        ("context contains created data",   test_context_contains_created_data),
        ("goal deletion nullifies goal_id", test_goal_deletion_nullifies_task_goal_id),
    ]),
    ("Sync", [
        ("sync",                            test_sync),
    ]),
    ("Pipeline", [
        ("insight (mock)",                  test_insight_mock),
        ("nudges (mock)",                   test_nudges_mock),
        ("run morning cycle",               test_run_morning_cycle),
    ]),
    ("Actions", [
        ("log action",                      test_log_action),
        ("sw action (unauthenticated)",     test_sw_action_unauthenticated),
    ]),
    ("Preferences", [
        ("get preferences",                 test_get_preferences),
        ("update preferences",              test_update_preferences),
        ("restore preferences",             test_restore_preferences),
    ]),
    ("Evaluation", [
        ("evaluation/today",                test_evaluation_today),
    ]),
    ("Push", [
        ("vapid public key",                test_vapid_public_key),
    ]),
    ("Cleanup", [
        ("cleanup",                         test_cleanup),
    ]),
]


def _main() -> None:
    print(f"\n{'=' * 60}")
    print("  Nudge — Full System Verification (WS5)")
    print(f"{'=' * 60}")
    print(f"  Server  : {BASE}")
    print(f"  User    : {USER_ID}")
    print()

    try:
        requests.get(BASE.replace("/api", ""), timeout=3)
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Cannot reach server — is it running?")
        print(f"          uvicorn api.main:app --reload\n")
        sys.exit(1)

    for section, tests in _ALL_TESTS:
        print(f"{section}:")
        for name, fn in tests:
            _run(name, fn)
            # Auth is a hard gate — nothing else works without a token
            if section == "Auth" and name == "login" and TOKEN is None:
                print("  Cannot continue without auth. Check APP_USER_ID/APP_PASSWORD in .env")
                sys.exit(1)
        print()

    print(f"{'=' * 60}")
    print(f"  Results : {_PASS} passed, {_FAIL} failed  ({_PASS + _FAIL} total)")
    if _FAIL:
        print(f"  Status  : FAIL")
    else:
        print(f"  Status  : PASS")
    print(f"{'=' * 60}\n")
    sys.exit(0 if _FAIL == 0 else 1)


if __name__ == "__main__":
    _main()
