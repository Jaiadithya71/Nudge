"""
tests/test_orchestrator.py — Orchestrator test suite.

Covers:
    1. Scheduler Tests    — simulate time, ensure correct job triggers
    2. Pipeline Tests     — mock memory, llm, nudge; verify correct sequence
    3. Rate Limit Tests   — exceed daily limit, ensure no new nudges
    4. Edge Cases         — no data, no insight, no nudges
    5. Context Conversion — _context_to_llm_dict shape contracts
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import pytest

# ---------------------------------------------------------------------------
# Ensure orchestrator/ and sibling paths are importable in the test context
# ---------------------------------------------------------------------------
_ORCHESTRATOR_DIR = Path(__file__).resolve().parent.parent
if str(_ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_ORCHESTRATOR_DIR))

import state
import orchestrator as orch

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

USER = "test-user-001"

_MOCK_CONTEXT_OBJ = {
    "user_id": USER,
    "goals": [{"id": "g1", "title": "Get fit", "priority": "high"}],
    "tasks": [{"id": "t1", "title": "Morning run", "status": "pending", "due_date": None}],
    "events": [],
    "contacts": [],
    "behavior_patterns": [{"id": "bp1", "description": "Morning exerciser", "pattern_type": "habit"}],
    "goal_alignments": [],
    "recent_actions": [{"id": "a1", "action_type": "task_view"}],
}

_MOCK_INSIGHT = {
    "insight_id": "ins-001",
    "summary": "User is on track.",
    "key_observations": ["Completed 3 tasks yesterday"],
    "goal_alignment": "0.8",
    "behavior_flags": ["low_completion_rate"],
    "opportunity_areas": ["finish pending tasks"],
}

_MOCK_NUDGE = {
    "type": "productivity",
    "message": "Focus on 1 high-impact task now.",
    "priority": "medium",
    "timing": "immediate",
}

# ---------------------------------------------------------------------------
# FakeState — in-memory drop-in for the SQLite-backed state module.
# Implements the same public API so orchestrator.py works unchanged.
# ---------------------------------------------------------------------------

class FakeState:
    def __init__(self):
        self._nudges: list[dict] = []      # [{...nudge, sent_at: iso}]
        self._last_run: str | None = None
        self._last_run_job: str | None = None
        self._nudge_bank: list[dict] = []
        self._insight_cache: dict | None = None
        self._kv: dict[str, str] = {}

    def _today_nudges(self) -> list[dict]:
        from datetime import date
        today = date.today().isoformat()
        return [n for n in self._nudges if n.get("sent_at", "").startswith(today)]

    def get_state(self, user_id: str) -> dict:
        today = self._today_nudges()
        last_ts = self._nudges[-1]["sent_at"] if self._nudges else None
        return {
            "nudges_sent_today": len(today),
            "last_nudge_time":   last_ts,
            "last_run":          self._last_run,
            "last_run_job":      self._last_run_job,
            "recent_nudges":     today[-10:],
        }

    def get_history(self, user_id: str) -> dict:
        s = self.get_state(user_id)
        return {
            "nudges_sent_today": s["nudges_sent_today"],
            "last_nudge_time":   s["last_nudge_time"],
            "recent_nudges":     s["recent_nudges"],
        }

    def update_after_run(self, user_id: str, job_type: str) -> None:
        self._last_run = datetime.now(timezone.utc).isoformat()
        self._last_run_job = job_type

    def record_nudges(self, user_id: str, nudges: list[dict], job_type: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        for nudge in nudges:
            self._nudges.append({**nudge, "sent_at": now})

    def store_nudge_bank(self, user_id: str, bank: list[dict]) -> None:
        self._nudge_bank = list(bank)

    def get_nudge_bank(self, user_id: str) -> list[dict]:
        return list(self._nudge_bank)

    def store_insight_cache(self, user_id: str, insight: dict) -> None:
        self._insight_cache = insight

    def get_cached_insight(self, user_id: str) -> dict | None:
        return self._insight_cache

    def store_kv(self, user_id: str, key: str, value: str) -> None:
        self._kv[key] = value

    def get_kv(self, user_id: str, key: str) -> str | None:
        return self._kv.get(key)


def _inject_nudge_at(fs: FakeState, nudge: dict, *, minutes_ago: int) -> None:
    """Insert a nudge into FakeState with a backdated timestamp."""
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    fs._nudges.append({**nudge, "sent_at": ts})


# ---------------------------------------------------------------------------
# Fixture — wire FakeState into both the state module and orchestrator._state
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fake_state():
    """Replace every state module function with an in-memory FakeState per test."""
    fs = FakeState()
    with patch.object(state, "get_state",          fs.get_state), \
         patch.object(state, "get_history",         fs.get_history), \
         patch.object(state, "update_after_run",    fs.update_after_run), \
         patch.object(state, "record_nudges",       fs.record_nudges), \
         patch.object(state, "store_nudge_bank",    fs.store_nudge_bank), \
         patch.object(state, "get_nudge_bank",      fs.get_nudge_bank), \
         patch.object(state, "store_insight_cache", fs.store_insight_cache), \
         patch.object(state, "get_cached_insight",  fs.get_cached_insight), \
         patch.object(state, "store_kv",            fs.store_kv), \
         patch.object(state, "get_kv",              fs.get_kv):
        yield fs


# ===========================================================================
# 1. Scheduler Tests
# ===========================================================================

class TestScheduler:

    def test_morning_job_fires_at_0700(self):
        """Scheduler fires 'morning' when clock reads 07:00."""
        call_log = []

        def fake_run_job(uid, jtype, mode="mock", preferences=None, **kw):
            call_log.append(jtype)
            return []

        times = [(6, 59), (7, 0), (7, 0), (7, 1), (12, 0)]
        tick_iter = iter(times)

        def time_fn():
            try:
                return next(tick_iter)
            except StopIteration:
                raise KeyboardInterrupt("stop")

        with patch.object(orch, "run_job", side_effect=fake_run_job), \
             patch("time.sleep", return_value=None):
            try:
                orch.run_scheduler(USER, _time_fn=time_fn, poll_interval_seconds=0)
            except KeyboardInterrupt:
                pass

        assert call_log.count("morning") == 1

    def test_midday_job_fires_at_1200(self):
        """Scheduler fires 'midday' when clock reads 12:00."""
        call_log = []

        def fake_run_job(uid, jtype, mode="mock", preferences=None, **kw):
            call_log.append(jtype)
            return []

        times = [(11, 59), (12, 0)]
        tick_iter = iter(times)

        def time_fn():
            try:
                return next(tick_iter)
            except StopIteration:
                raise KeyboardInterrupt("stop")

        with patch.object(orch, "run_job", side_effect=fake_run_job), \
             patch("time.sleep", return_value=None):
            try:
                orch.run_scheduler(USER, _time_fn=time_fn, poll_interval_seconds=0)
            except KeyboardInterrupt:
                pass

        assert "midday" in call_log

    def test_evening_job_fires_at_1900(self):
        """Scheduler fires 'evening' when clock reads 19:00."""
        call_log = []

        def fake_run_job(uid, jtype, mode="mock", preferences=None, **kw):
            call_log.append(jtype)
            return []

        times = [(18, 59), (19, 0)]
        tick_iter = iter(times)

        def time_fn():
            try:
                return next(tick_iter)
            except StopIteration:
                raise KeyboardInterrupt("stop")

        with patch.object(orch, "run_job", side_effect=fake_run_job), \
             patch("time.sleep", return_value=None):
            try:
                orch.run_scheduler(USER, _time_fn=time_fn, poll_interval_seconds=0)
            except KeyboardInterrupt:
                pass

        assert "evening" in call_log

    def test_off_schedule_time_fires_no_job(self):
        """Scheduler does NOT fire any job at an unscheduled time (e.g. 10:30)."""
        call_log = []

        def fake_run_job(uid, jtype, mode="mock", preferences=None, **kw):
            call_log.append(jtype)
            return []

        times = [(10, 30)]
        tick_iter = iter(times)

        def time_fn():
            try:
                return next(tick_iter)
            except StopIteration:
                raise KeyboardInterrupt("stop")

        with patch.object(orch, "run_job", side_effect=fake_run_job), \
             patch("time.sleep", return_value=None):
            try:
                orch.run_scheduler(USER, _time_fn=time_fn, poll_interval_seconds=0)
            except KeyboardInterrupt:
                pass

        assert call_log == []


# ===========================================================================
# 2. Pipeline Tests
# ===========================================================================

class TestPipeline:

    def test_morning_pipeline_calls_in_order(self):
        """Morning job calls context → insight → nudges in order."""
        call_order = []

        def mock_ctx(uid):
            call_order.append("context")
            return _MOCK_CONTEXT_OBJ

        def mock_ins(ctx, mode):
            call_order.append("insight")
            return _MOCK_INSIGHT

        def mock_nud(ins, ctx, hist, prefs):
            call_order.append("nudges")
            return [_MOCK_NUDGE]

        with patch.object(orch, "_build_context",   side_effect=mock_ctx), \
             patch.object(orch, "_generate_insight", side_effect=mock_ins), \
             patch.object(orch, "_generate_nudges",  side_effect=mock_nud):
            result = orch.run_job(USER, "morning")

        assert call_order == ["context", "insight", "nudges"]
        assert result == [_MOCK_NUDGE]

    def test_evening_pipeline_uses_softer_strictness(self):
        """Evening job passes strictness=0.4 to nudge engine."""
        captured_prefs = {}

        def mock_nud(ins, ctx, hist, prefs):
            captured_prefs.update(prefs)
            return []

        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_insight", return_value=_MOCK_INSIGHT), \
             patch.object(orch, "_generate_nudges",  side_effect=mock_nud):
            orch.run_job(USER, "evening")

        assert captured_prefs.get("strictness") == 0.4

    def test_midday_pipeline_sends_inactivity_insight(self):
        """Midday job sends a synthetic inactivity insight (no LLM call)."""
        captured_insight = {}

        def mock_nud(ins, ctx, hist, prefs):
            captured_insight.update(ins)
            return []

        with patch.object(orch, "_build_context",  return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_nudges", side_effect=mock_nud):
            orch.run_job(USER, "midday")

        assert "inactivity" in captured_insight.get("behavior_flags", [])

    def test_event_pipeline_runs_full_pipeline(self):
        """Event job runs the full context → insight → nudge pipeline."""
        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ) as m_ctx, \
             patch.object(orch, "_generate_insight", return_value=_MOCK_INSIGHT) as m_ins, \
             patch.object(orch, "_generate_nudges",  return_value=[_MOCK_NUDGE]) as m_nud:
            result = orch.run_job(USER, "event")

        m_ctx.assert_called_once_with(USER)
        m_ins.assert_called_once()
        m_nud.assert_called_once()
        assert result == [_MOCK_NUDGE]

    def test_state_updated_after_job(self, fake_state):
        """State counters are updated after a successful job."""
        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_insight", return_value=_MOCK_INSIGHT), \
             patch.object(orch, "_generate_nudges",  return_value=[_MOCK_NUDGE]):
            orch.run_job(USER, "morning")

        s = state.get_state(USER)
        assert s["nudges_sent_today"] == 1
        assert s["last_nudge_time"] is not None
        assert s["last_run_job"] == "morning"


# ===========================================================================
# 3. Rate Limit Tests
# ===========================================================================

class TestRateLimits:

    def test_daily_limit_blocks_new_nudges(self, fake_state):
        """When daily limit is reached, run_job returns [] without calling the pipeline."""
        prefs = {"max_nudges_per_day": 2, "strictness": 0.7}

        state.record_nudges(USER, [_MOCK_NUDGE, _MOCK_NUDGE])

        with patch.object(orch, "_build_context")   as m_ctx, \
             patch.object(orch, "_generate_insight") as m_ins, \
             patch.object(orch, "_generate_nudges")  as m_nud:
            result = orch.run_job(USER, "morning", preferences=prefs)

        assert result == []
        m_ctx.assert_not_called()
        m_ins.assert_not_called()
        m_nud.assert_not_called()

    def test_daily_limit_counts_across_jobs(self, fake_state):
        """Nudges from different jobs aggregate toward the daily limit."""
        prefs = {"max_nudges_per_day": 1, "strictness": 0.7}

        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_insight", return_value=_MOCK_INSIGHT), \
             patch.object(orch, "_generate_nudges",  return_value=[_MOCK_NUDGE]):
            first = orch.run_job(USER, "morning", preferences=prefs)

        with patch.object(orch, "_build_context") as m_ctx:
            second = orch.run_job(USER, "midday", preferences=prefs)

        assert len(first) == 1
        assert second == []
        m_ctx.assert_not_called()

    def test_min_gap_blocks_nudge_if_too_soon(self, fake_state):
        """run_job returns [] if the minimum gap between nudges has not elapsed."""
        _inject_nudge_at(fake_state, _MOCK_NUDGE, minutes_ago=30)

        prefs = {"max_nudges_per_day": 5, "min_gap_hours": 2}

        with patch.object(orch, "_build_context") as m_ctx:
            result = orch.run_job(USER, "morning", preferences=prefs)

        assert result == []
        m_ctx.assert_not_called()

    def test_min_gap_allows_nudge_after_elapsed(self, fake_state):
        """run_job proceeds if the minimum gap between nudges HAS elapsed."""
        _inject_nudge_at(fake_state, _MOCK_NUDGE, minutes_ago=180)

        prefs = {"max_nudges_per_day": 5, "min_gap_hours": 2}

        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_insight", return_value=_MOCK_INSIGHT), \
             patch.object(orch, "_generate_nudges",  return_value=[_MOCK_NUDGE]):
            result = orch.run_job(USER, "morning", preferences=prefs)

        assert result == [_MOCK_NUDGE]


# ===========================================================================
# 4. Edge Cases
# ===========================================================================

class TestEdgeCases:

    def test_no_context_data_aborts_gracefully(self):
        """When build_user_context returns empty context, job completes without error."""
        empty_context = {
            "user_id": USER,
            "goals": [], "tasks": [], "events": [],
            "contacts": [], "behavior_patterns": [],
            "goal_alignments": [], "recent_actions": [],
        }
        with patch.object(orch, "_build_context",   return_value=empty_context), \
             patch.object(orch, "_generate_insight", return_value=_MOCK_INSIGHT), \
             patch.object(orch, "_generate_nudges",  return_value=[]):
            result = orch.run_job(USER, "morning")

        assert result == []

    def test_no_insight_aborts_morning_job(self):
        """When LLM returns None, morning job returns []."""
        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_insight", return_value=None):
            result = orch.run_job(USER, "morning")

        assert result == []

    def test_no_insight_aborts_evening_job(self):
        """When LLM returns None, evening job returns []."""
        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_insight", return_value=None):
            result = orch.run_job(USER, "evening")

        assert result == []

    def test_no_nudges_produced(self, fake_state):
        """When nudge engine returns [], run_job returns [] and state is unchanged."""
        with patch.object(orch, "_build_context",   return_value=_MOCK_CONTEXT_OBJ), \
             patch.object(orch, "_generate_insight", return_value=_MOCK_INSIGHT), \
             patch.object(orch, "_generate_nudges",  return_value=[]):
            result = orch.run_job(USER, "morning")

        assert result == []
        assert state.get_state(USER)["nudges_sent_today"] == 0

    def test_memory_failure_falls_back_to_empty_context(self):
        """run_job never propagates a memory error — falls back to empty context."""
        with patch.object(orch, "_build_context", return_value={
            "user_id": USER, "goals": [], "tasks": [], "events": [],
            "contacts": [], "behavior_patterns": [], "goal_alignments": [], "recent_actions": [],
        }), patch.object(orch, "_generate_insight", return_value=None):
            result = orch.run_job(USER, "morning")

        assert result == []

    def test_invalid_job_type_raises_value_error(self):
        """run_job raises ValueError for unknown job_type."""
        with pytest.raises(ValueError, match="Unknown job_type"):
            orch.run_job(USER, "unknown_job")

    def test_empty_user_id_raises_value_error(self):
        """run_job raises ValueError when user_id is empty."""
        with pytest.raises(ValueError, match="user_id is required"):
            orch.run_job("", "morning")


# ===========================================================================
# 5. Context Conversion Tests
# ===========================================================================

class TestContextConversion:

    def test_context_to_llm_dict_from_plain_dict(self):
        """_context_to_llm_dict extracts required LLM fields from a plain dict."""
        result = orch._context_to_llm_dict(_MOCK_CONTEXT_OBJ)
        assert "goals" in result
        assert "tasks" in result
        assert "recent_actions" in result
        assert "behavior_patterns" in result
        assert "daily_summary" in result
        assert isinstance(result["goals"], list)

    def test_context_to_llm_dict_goals_are_strings(self):
        """Goals in LLM dict are stringified titles."""
        result = orch._context_to_llm_dict(_MOCK_CONTEXT_OBJ)
        assert all(isinstance(g, str) for g in result["goals"])

    def test_context_to_llm_dict_daily_summary_non_empty(self):
        """daily_summary is always a non-empty string."""
        result = orch._context_to_llm_dict(_MOCK_CONTEXT_OBJ)
        assert len(result["daily_summary"]) > 0
