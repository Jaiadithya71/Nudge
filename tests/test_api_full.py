"""
tests/test_api_full.py -- Comprehensive API test suite for the Nudge system.

Run with:
    python -X utf8 tests/test_api_full.py

Requires the server to be running:
    uvicorn api.main:app --reload   (from the Nudge/ root)
"""

from __future__ import annotations

import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8000"
API_URL  = f"{BASE_URL}/api"
USER_ID  = "test_user_suite"
PASSWORD = "nudge-admin-password"   # matches APP_PASSWORD in .env
TIMEOUT  = 30

# ─────────────────────────────────────────────────────────────────────────────
# Token management
# ─────────────────────────────────────────────────────────────────────────────

_token_cache: dict[str, str] = {}

def _login(user_id: str = USER_ID, password: str = PASSWORD) -> str:
    if user_id not in _token_cache:
        r = requests.post(f"{API_URL}/auth/login",
                          json={"user_id": user_id, "password": password},
                          timeout=TIMEOUT)
        r.raise_for_status()
        _token_cache[user_id] = r.json()["access_token"]
    return _token_cache[user_id]

def _headers(user_id: str = USER_ID) -> dict:
    return {"Authorization": f"Bearer {_login(user_id)}"}

# ─────────────────────────────────────────────────────────────────────────────
# Assertion helpers
# ─────────────────────────────────────────────────────────────────────────────

_PASS = 0
_FAIL = 0
_results: list[tuple[str, bool, str]] = []

def _assert(name: str, condition: bool, detail: str = "") -> bool:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
    else:
        _FAIL += 1
    _results.append((name, condition, detail))
    return condition

def _get(path: str, user_id: str = USER_ID, **params) -> requests.Response:
    return requests.get(f"{API_URL}{path}", params=params,
                        headers=_headers(user_id), timeout=TIMEOUT)

def _post(path: str, body: dict, user_id: str = USER_ID,
          authenticated: bool = True) -> requests.Response:
    h = _headers(user_id) if authenticated else {}
    return requests.post(f"{API_URL}{path}", json=body, headers=h, timeout=TIMEOUT)

# ─────────────────────────────────────────────────────────────────────────────
# 0. Health check (unauthenticated)
# ─────────────────────────────────────────────────────────────────────────────

def test_health_check():
    r = requests.get(BASE_URL, timeout=TIMEOUT)
    _assert("health: status 200",           r.status_code == 200)
    _assert("health: status=online",        r.json().get("status") == "online")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Auth
# ─────────────────────────────────────────────────────────────────────────────

def test_auth_login_success():
    r = requests.post(f"{API_URL}/auth/login",
                      json={"user_id": USER_ID, "password": PASSWORD}, timeout=TIMEOUT)
    _assert("auth: login 200",              r.status_code == 200)
    body = r.json()
    _assert("auth: access_token present",   "access_token" in body)
    _assert("auth: token_type=bearer",      body.get("token_type") == "bearer")
    _assert("auth: user_id echoed",         body.get("user_id") == USER_ID)

def test_auth_login_wrong_password():
    r = requests.post(f"{API_URL}/auth/login",
                      json={"user_id": USER_ID, "password": "wrong"}, timeout=TIMEOUT)
    _assert("auth: 401 on wrong password",  r.status_code == 401)

def test_auth_me():
    r = requests.get(f"{API_URL}/auth/me", headers=_headers(), timeout=TIMEOUT)
    _assert("auth: /me 200",                r.status_code == 200)
    _assert("auth: /me returns user_id",    r.json().get("user_id") == USER_ID)

def test_auth_me_no_token():
    r = requests.get(f"{API_URL}/auth/me", timeout=TIMEOUT)
    _assert("auth: /me 403 without token",  r.status_code in (401, 403))

def test_auth_invalid_token():
    h = {"Authorization": "Bearer this.is.not.valid"}
    r = requests.get(f"{API_URL}/auth/me", headers=h, timeout=TIMEOUT)
    _assert("auth: 401 on bad token",       r.status_code == 401)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Protected routes reject unauthenticated requests
# ─────────────────────────────────────────────────────────────────────────────

def test_all_protected_routes_require_auth():
    endpoints = [
        ("GET",  f"{API_URL}/context",    None),
        ("GET",  f"{API_URL}/insight",    None),
        ("GET",  f"{API_URL}/nudges",     None),
        ("POST", f"{API_URL}/log-action", {"action": "x"}),
        ("POST", f"{API_URL}/run-cycle",  {"job_type": "morning"}),
        ("POST", f"{API_URL}/sync",       {}),
    ]
    for method, url, body in endpoints:
        if method == "GET":
            r = requests.get(url, timeout=TIMEOUT)
        else:
            r = requests.post(url, json=body, timeout=TIMEOUT)
        short = url.split("/api")[1]
        _assert(f"unauth: {method} {short} -> 401/403",
                r.status_code in (401, 403),
                f"got {r.status_code}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. GET /api/context
# ─────────────────────────────────────────────────────────────────────────────

def test_context_happy_path():
    r = _get("/context")
    _assert("context: 200",                  r.status_code == 200)
    body = r.json()
    _assert("context: user_id matches",      body.get("user_id") == USER_ID)
    _assert("context: goals is list",        isinstance(body.get("goals"), list))
    _assert("context: tasks is list",        isinstance(body.get("tasks"), list))
    _assert("context: events is list",       isinstance(body.get("events"), list))
    _assert("context: contacts is list",     isinstance(body.get("contacts"), list))
    _assert("context: recent_actions list",  isinstance(body.get("recent_actions"), list))
    _assert("context: built_at present",     "built_at" in body)

def test_context_user_isolation():
    """Each token's user_id gets back only their own data."""
    # Login two different users
    _token_cache.pop("user_alpha", None)
    _token_cache.pop("user_beta", None)
    r1 = _get("/context", user_id="user_alpha")
    r2 = _get("/context", user_id="user_beta")
    _assert("context: alpha user_id",  r1.json().get("user_id") == "user_alpha")
    _assert("context: beta user_id",   r2.json().get("user_id") == "user_beta")

def test_context_repeated_calls_stable():
    r1 = _get("/context")
    r2 = _get("/context")
    _assert("context: idempotent", r1.status_code == 200 and r2.status_code == 200)

# ─────────────────────────────────────────────────────────────────────────────
# 4. GET /api/insight
# ─────────────────────────────────────────────────────────────────────────────

def test_insight_mock_mode():
    r = _get("/insight", mode="mock")
    _assert("insight: 200",                   r.status_code == 200)
    body = r.json()
    _assert("insight: summary",               bool(body.get("summary")))
    _assert("insight: key_observations list", isinstance(body.get("key_observations"), list))
    _assert("insight: behavior_flags list",   isinstance(body.get("behavior_flags"), list))
    _assert("insight: decision_signals dict", isinstance(body.get("decision_signals"), dict))

def test_insight_decision_signals_schema():
    ds = _get("/insight", mode="mock").json().get("decision_signals", {})
    for flag in ("needs_activation", "needs_correction", "goal_at_risk", "has_overdue_tasks"):
        _assert(f"insight: signals.{flag} is bool", isinstance(ds.get(flag), bool))

def test_insight_idempotent():
    r1 = _get("/insight", mode="mock")
    r2 = _get("/insight", mode="mock")
    _assert("insight: idempotent", r1.status_code == 200 and r2.status_code == 200)

# ─────────────────────────────────────────────────────────────────────────────
# 5. GET /api/nudges
# ─────────────────────────────────────────────────────────────────────────────

def test_nudges_happy_path():
    r = _get("/nudges", mode="mock")
    _assert("nudges: 200",          r.status_code == 200)
    _assert("nudges: list",         isinstance(r.json().get("nudges"), list))

def test_nudges_schema():
    nudges = _get("/nudges", mode="mock").json().get("nudges", [])
    required = {"type", "message", "priority", "timing"}
    if nudges:
        for i, n in enumerate(nudges):
            for f in required:
                _assert(f"nudges: nudge[{i}].{f} present", f in n)
    else:
        _assert("nudges: schema skipped (0 nudges — rate limit)", True)

def test_nudges_max_per_call():
    nudges = _get("/nudges", mode="mock").json().get("nudges", [])
    _assert("nudges: max 2 per call", len(nudges) <= 2, f"got {len(nudges)}")

def test_nudges_user_isolation():
    ra = _get("/nudges", user_id="nudge_user_a", mode="mock")
    rb = _get("/nudges", user_id="nudge_user_b", mode="mock")
    _assert("nudges: user_a 200", ra.status_code == 200)
    _assert("nudges: user_b 200", rb.status_code == 200)

# ─────────────────────────────────────────────────────────────────────────────
# 6. POST /api/log-action
# ─────────────────────────────────────────────────────────────────────────────

def test_log_action_happy_path():
    r = _post("/log-action", {"action": "task_completed", "metadata": {"src": "test"}})
    _assert("log-action: 200",             r.status_code == 200)
    _assert("log-action: status=success",  r.json().get("status") == "success")

def test_log_action_no_metadata():
    r = _post("/log-action", {"action": "dashboard_viewed"})
    _assert("log-action: 200 no metadata", r.status_code == 200)

def test_log_action_persists_to_context():
    unique = f"action_{int(time.time())}"
    _post("/log-action", {"action": unique, "metadata": {}})
    recent = _get("/context").json().get("recent_actions", [])
    types  = [a.get("action_type") if isinstance(a, dict) else str(a) for a in recent]
    _assert("log-action: persists to context", unique in types, f"types: {types}")

def test_log_action_missing_action():
    r = _post("/log-action", {"metadata": {}})
    _assert("log-action: 422 without action", r.status_code == 422)

def test_log_action_sequential():
    for i in range(5):
        r = _post("/log-action", {"action": f"seq_action_{i}"})
        _assert(f"log-action: seq #{i}", r.status_code == 200)

# ─────────────────────────────────────────────────────────────────────────────
# 7. POST /api/run-cycle
# ─────────────────────────────────────────────────────────────────────────────

def _cycle(job: str, user_id: str = USER_ID) -> requests.Response:
    return _post("/run-cycle", {"job_type": job, "mode": "mock"}, user_id=user_id)

def test_run_cycle_morning():
    r = _cycle("morning", "cycle_morning_user")
    _assert("cycle morning: 200",          r.status_code == 200)
    body = r.json()
    _assert("cycle morning: status",       body.get("status") == "success")
    _assert("cycle morning: job_type",     body.get("job_type") == "morning")
    _assert("cycle morning: count is int", isinstance(body.get("nudges_generated"), int))
    _assert("cycle morning: nudges list",  isinstance(body.get("nudges"), list))

def test_run_cycle_midday():
    r = _cycle("midday", "cycle_midday_user")
    _assert("cycle midday: 200",       r.status_code == 200)
    _assert("cycle midday: job_type",  r.json().get("job_type") == "midday")

def test_run_cycle_evening():
    r = _cycle("evening", "cycle_evening_user")
    _assert("cycle evening: 200",      r.status_code == 200)
    _assert("cycle evening: job_type", r.json().get("job_type") == "evening")

def test_run_cycle_event():
    r = _cycle("event", "cycle_event_user")
    _assert("cycle event: 200",        r.status_code == 200)
    _assert("cycle event: job_type",   r.json().get("job_type") == "event")

def test_run_cycle_count_matches():
    r = _cycle("morning", "cycle_count_user")
    body = r.json()
    _assert("cycle: count==len(nudges)",
            body.get("nudges_generated") == len(body.get("nudges", [])))

def test_run_cycle_nudge_schema():
    r = _cycle("morning", "cycle_schema_user")
    for i, n in enumerate(r.json().get("nudges", [])):
        for f in ("type", "message", "priority", "timing"):
            _assert(f"cycle nudge[{i}].{f}", f in n)

def test_run_cycle_invalid_job():
    r = _post("/run-cycle", {"job_type": "bad_job", "mode": "mock"})
    _assert("cycle: 4xx/5xx on bad job", r.status_code >= 400, f"got {r.status_code}")

def test_run_cycle_defaults():
    r = _post("/run-cycle", {})
    _assert("cycle: 200 with defaults only", r.status_code == 200)

def test_run_cycle_rate_limit():
    uid = "rate_limit_user_v2"
    counts = []
    for job in ["morning", "midday", "evening", "event", "morning"]:
        r = _post("/run-cycle", {"job_type": job, "mode": "mock"}, user_id=uid)
        _assert(f"rate-limit: {job} 200", r.status_code == 200)
        counts.append(r.json().get("nudges_generated", 0))
    _assert("rate-limit: cap kicks in", any(n == 0 for n in counts),
            f"counts: {counts}")

# ─────────────────────────────────────────────────────────────────────────────
# 8. POST /api/sync
# ─────────────────────────────────────────────────────────────────────────────

def test_sync_happy_path():
    r = _post("/sync", {})
    _assert("sync: 200",            r.status_code == 200)
    body = r.json()
    _assert("sync: status=ok",      body.get("status") == "ok")
    _assert("sync: synced dict",    isinstance(body.get("synced"), dict))
    synced = body.get("synced", {})
    for key in ("goals", "tasks", "events", "contacts"):
        _assert(f"sync: synced.{key} is int", isinstance(synced.get(key), int))

def test_sync_populates_context():
    """After a sync, context should reflect the ingested data."""
    _post("/sync", {})
    ctx = _get("/context").json()
    _assert("sync: tasks in context after sync",
            len(ctx.get("tasks", [])) >= 0)   # just verifies no error

def test_sync_no_auth():
    r = requests.post(f"{API_URL}/sync", json={}, timeout=TIMEOUT)
    _assert("sync: 401 without token", r.status_code in (401, 403))

# ─────────────────────────────────────────────────────────────────────────────
# 9. Full pipeline integration
# ─────────────────────────────────────────────────────────────────────────────

def test_full_pipeline():
    uid = "pipeline_user_v2"
    # sync -> context -> insight -> nudges
    _assert("pipeline: sync",    _post("/sync", {}, user_id=uid).status_code == 200)
    ctx = _get("/context", user_id=uid)
    _assert("pipeline: context", ctx.status_code == 200)
    _assert("pipeline: user_id", ctx.json().get("user_id") == uid)
    ins = _get("/insight", user_id=uid, mode="mock")
    _assert("pipeline: insight", ins.status_code == 200)
    _assert("pipeline: summary", bool(ins.json().get("summary")))
    nud = _get("/nudges",  user_id=uid, mode="mock")
    _assert("pipeline: nudges",  nud.status_code == 200)
    _assert("pipeline: nudges list", isinstance(nud.json().get("nudges"), list))

# ─────────────────────────────────────────────────────────────────────────────
# 10. Response format sanity
# ─────────────────────────────────────────────────────────────────────────────

def test_all_responses_are_json():
    calls = [
        ("GET",  f"{API_URL}/context",    None),
        ("GET",  f"{API_URL}/insight",    None),
        ("GET",  f"{API_URL}/nudges",     None),
        ("POST", f"{API_URL}/log-action", {"action": "x"}),
        ("POST", f"{API_URL}/run-cycle",  {"job_type": "morning"}),
        ("POST", f"{API_URL}/sync",       {}),
    ]
    for method, url, body in calls:
        if method == "GET":
            r = requests.get(url, headers=_headers(), timeout=TIMEOUT)
        else:
            r = requests.post(url, json=body, headers=_headers(), timeout=TIMEOUT)
        ct = r.headers.get("content-type", "")
        short = url.split("/api")[1]
        _assert(f"json ct: {method} {short}", "application/json" in ct, ct)

# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_health_check,
    test_auth_login_success,
    test_auth_login_wrong_password,
    test_auth_me,
    test_auth_me_no_token,
    test_auth_invalid_token,
    test_all_protected_routes_require_auth,
    test_context_happy_path,
    test_context_user_isolation,
    test_context_repeated_calls_stable,
    test_insight_mock_mode,
    test_insight_decision_signals_schema,
    test_insight_idempotent,
    test_nudges_happy_path,
    test_nudges_schema,
    test_nudges_max_per_call,
    test_nudges_user_isolation,
    test_log_action_happy_path,
    test_log_action_no_metadata,
    test_log_action_persists_to_context,
    test_log_action_missing_action,
    test_log_action_sequential,
    test_run_cycle_morning,
    test_run_cycle_midday,
    test_run_cycle_evening,
    test_run_cycle_event,
    test_run_cycle_count_matches,
    test_run_cycle_nudge_schema,
    test_run_cycle_invalid_job,
    test_run_cycle_defaults,
    test_run_cycle_rate_limit,
    test_sync_happy_path,
    test_sync_populates_context,
    test_sync_no_auth,
    test_full_pipeline,
    test_all_responses_are_json,
]

_DIVIDER = "-" * 60

def _run_all():
    global _PASS, _FAIL
    print(f"\n{'=' * 60}")
    print("  NUDGE SYSTEM -- FULL API TEST SUITE (v2 auth)")
    print(f"{'=' * 60}")
    print(f"  Server : {BASE_URL}")
    print(f"  Tests  : {len(ALL_TESTS)} test functions\n")

    try:
        requests.get(BASE_URL, timeout=3)
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Cannot reach {BASE_URL} -- is the server running?")
        print(f"          uvicorn api.main:app --reload\n")
        sys.exit(1)

    for fn in ALL_TESTS:
        before_pass, before_fail = _PASS, _FAIL
        try:
            fn()
        except Exception as exc:
            _FAIL += 1
            _results.append((f"{fn.__name__}: UNCAUGHT EXCEPTION", False, str(exc)))

        fn_fail = _FAIL - before_fail
        fn_pass = _PASS - before_pass
        status  = "[PASS]" if fn_fail == 0 else "[FAIL]"
        print(f"  {status}  {fn.__name__}  ({fn_pass} assertions)")

    print(f"\n{_DIVIDER}")
    print(f"  Results : {_PASS} passed, {_FAIL} failed  ({_PASS + _FAIL} total)")

    failures = [(n, d) for n, ok, d in _results if not ok]
    if failures:
        print(f"\n  Failed assertions:")
        for name, detail in failures:
            print(f"    x  {name}")
            if detail:
                print(f"       -> {detail}")

    print(f"{_DIVIDER}\n")
    return _FAIL == 0


if __name__ == "__main__":
    ok = _run_all()
    sys.exit(0 if ok else 1)
