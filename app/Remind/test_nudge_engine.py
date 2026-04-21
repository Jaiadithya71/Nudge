"""
NUDGE ENGINE — test_nudge_engine.py
=====================================
Tests aligned with CONTRACT.md, SPEC.md, and IMPLEMENTATION_GUIDE.md.

Public API: generate_nudges(insight, user_context, history, preferences) -> list

The engine reads decision_signals (dict of booleans) from insight:
  needs_correction / has_overdue_tasks  → correction  (high)
  goal_at_risk                          → strategic   (medium)
  needs_activation                      → activation  (low)
  behavior_flags contains evening_reflection → reflection (low)

Run:  python -m pytest test_nudge_engine.py -v
  or: python test_nudge_engine.py
"""

import unittest

from nudge_engine import generate_nudges, _get_task_context, _pick_task_aware_message


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

USER_CTX = {}  # Empty user context — valid for unit tests


def _insight(
    signals: dict | None = None,
    flags: list | None = None,
    goal_alignment: float = 0.5,
    summary: str = "test",
) -> dict:
    return {
        "summary": summary,
        "behavior_flags": flags or [],
        "goal_alignment": goal_alignment,
        "decision_signals": signals or {},
    }


def _history(sent: int = 0, recent_types: list | None = None) -> dict:
    recent = [{"type": t} for t in (recent_types or [])]
    return {
        "nudges_sent_today": sent,
        "last_nudge_time":   None,
        "recent_nudges":     recent,
    }


def _prefs(
    max_nudges: int = 3,
    strictness: float = 0.7,
    windows: list | None = None,
) -> dict:
    if windows is None:
        windows = [{"start": "00:00", "end": "23:59"}]  # always open
    return {
        "max_nudges_per_day":   max_nudges,
        "strictness":           strictness,
        "allowed_time_windows": windows,
    }


# ---------------------------------------------------------------------------
# Contract guarantees
# ---------------------------------------------------------------------------

class TestContractGuarantees(unittest.TestCase):
    """Verify all guarantees stated in CONTRACT.md."""

    def test_returns_list(self):
        result = generate_nudges(_insight({"has_overdue_tasks": True}), USER_CTX, _history(), _prefs())
        self.assertIsInstance(result, list)

    def test_max_2_nudges_per_call(self):
        """CONTRACT: max 2 nudges per call, even with many triggers."""
        ins = _insight({"has_overdue_tasks": True, "goal_at_risk": True, "needs_activation": True})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        self.assertLessEqual(len(result), 2)

    def test_no_duplicate_types_within_call(self):
        """CONTRACT: no duplicate nudge types returned in a single call."""
        ins = _insight({"has_overdue_tasks": True, "goal_at_risk": True, "needs_activation": True})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        types = [n["type"] for n in result]
        self.assertEqual(len(types), len(set(types)))

    def test_no_duplicate_types_against_history(self):
        """CONTRACT: no nudge type that already appears in recent_nudges."""
        ins = _insight({"has_overdue_tasks": True})
        hist = _history(sent=0, recent_types=["correction"])
        result = generate_nudges(ins, USER_CTX, hist, _prefs())
        for nudge in result:
            self.assertNotEqual(nudge["type"], "correction")

    def test_respects_daily_limit_hard_stop(self):
        """CONTRACT: if sent_today >= max, return empty list."""
        ins = _insight({"has_overdue_tasks": True, "goal_at_risk": True})
        result = generate_nudges(ins, USER_CTX, _history(sent=3), _prefs(max_nudges=3))
        self.assertEqual(result, [])

    def test_output_structure_complete(self):
        """Every nudge in output has all 4 required keys."""
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        self.assertGreater(len(result), 0)
        for nudge in result:
            for key in ("type", "message", "priority", "timing"):
                self.assertIn(key, nudge)


# ---------------------------------------------------------------------------
# Decision Engine — IMPLEMENTATION_GUIDE Step 1
# ---------------------------------------------------------------------------

class TestDecisionEngine(unittest.TestCase):

    def test_overdue_tasks_triggers_correction(self):
        """has_overdue_tasks signal -> HIGH priority correction."""
        result = generate_nudges(_insight({"has_overdue_tasks": True}), USER_CTX, _history(), _prefs())
        self.assertIn("correction", [n["type"] for n in result])

    def test_needs_correction_triggers_correction(self):
        """needs_correction signal also triggers correction."""
        result = generate_nudges(_insight({"needs_correction": True}), USER_CTX, _history(), _prefs())
        self.assertIn("correction", [n["type"] for n in result])

    def test_correction_is_high_priority(self):
        result = generate_nudges(_insight({"has_overdue_tasks": True}), USER_CTX, _history(), _prefs())
        correction = next(n for n in result if n["type"] == "correction")
        self.assertEqual(correction["priority"], "high")

    def test_goal_at_risk_triggers_strategic(self):
        """goal_at_risk signal -> MEDIUM priority strategic."""
        result = generate_nudges(_insight({"goal_at_risk": True}), USER_CTX, _history(), _prefs())
        self.assertIn("strategic", [n["type"] for n in result])

    def test_strategic_is_medium_priority(self):
        result = generate_nudges(_insight({"goal_at_risk": True}), USER_CTX, _history(), _prefs())
        strategic = next(n for n in result if n["type"] == "strategic")
        self.assertEqual(strategic["priority"], "medium")

    def test_needs_activation_triggers_activation(self):
        """needs_activation signal -> activation nudge."""
        result = generate_nudges(_insight({"needs_activation": True}), USER_CTX, _history(), _prefs())
        self.assertIn("activation", [n["type"] for n in result])

    def test_evening_reflection_flag_triggers_reflection(self):
        """evening_reflection in behavior_flags -> reflection nudge."""
        ins = _insight(flags=["evening_reflection"])
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        self.assertIn("reflection", [n["type"] for n in result])

    def test_no_signals_returns_empty(self):
        ins = _insight({})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Priority Assignment — IMPLEMENTATION_GUIDE Step 2
# ---------------------------------------------------------------------------

class TestPriorityAssignment(unittest.TestCase):

    def test_high_priority_before_low(self):
        """High-priority nudges appear before low-priority ones in result."""
        ins = _insight({"has_overdue_tasks": True, "needs_activation": True})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        if len(result) >= 2:
            from nudge_engine import PRIORITY_ORDER
            priorities = [PRIORITY_ORDER[n["priority"]] for n in result]
            self.assertEqual(priorities, sorted(priorities))

    def test_valid_priorities(self):
        ins = _insight({"has_overdue_tasks": True, "goal_at_risk": True, "needs_activation": True})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        for nudge in result:
            self.assertIn(nudge["priority"], ("low", "medium", "high"))


# ---------------------------------------------------------------------------
# Nudge Types — IMPLEMENTATION_GUIDE Step 3
# ---------------------------------------------------------------------------

class TestNudgeTypes(unittest.TestCase):

    def test_signal_to_type_mapping(self):
        """Each signal produces the expected nudge type."""
        cases = [
            ({"has_overdue_tasks": True}, "correction"),
            ({"needs_correction": True},  "correction"),
            ({"goal_at_risk": True},       "strategic"),
            ({"needs_activation": True},   "activation"),
        ]
        for signals, expected_type in cases:
            result = generate_nudges(_insight(signals), USER_CTX, _history(), _prefs())
            types = [n["type"] for n in result]
            self.assertIn(expected_type, types, f"Expected {expected_type} from signals {signals}")

    def test_timing_is_valid(self):
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        for nudge in result:
            self.assertIn(nudge["timing"], ("immediate", "scheduled"))


# ---------------------------------------------------------------------------
# Tone enforcement — IMPLEMENTATION_GUIDE Step 5
# ---------------------------------------------------------------------------

class TestToneEnforcement(unittest.TestCase):

    def test_message_is_non_empty_string(self):
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, USER_CTX, _history(), _prefs())
        for nudge in result:
            self.assertIsInstance(nudge["message"], str)
            self.assertGreater(len(nudge["message"]), 10)

    def test_strictness_configurable(self):
        """Strictness 1.0 always returns strict messages (no supportive)."""
        supportive_keywords = [
            "okay to stumble", "small steps", "capable", "gentle nudge",
            "you've done it", "focused 25-minute", "it's been quiet",
            "one small thing", "reflection time", "one honest look",
            "small step",
        ]
        ins = _insight({"has_overdue_tasks": True})
        prefs = _prefs(strictness=1.0)
        supportive_count = 0
        for _ in range(50):
            result = generate_nudges(ins, USER_CTX, _history(), prefs)
            for nudge in result:
                if any(kw.lower() in nudge["message"].lower() for kw in supportive_keywords):
                    supportive_count += 1
        self.assertEqual(supportive_count, 0, "strictness=1.0 should never return supportive messages")

    def test_default_strictness_leans_strict(self):
        """Default strictness (0.7) should produce strict messages ~65-85% of the time."""
        supportive_keywords = [
            "okay to stumble", "small steps", "gentle nudge", "capable",
            "you've done it", "it's been quiet", "one small thing", "small step",
        ]
        ins = _insight({"has_overdue_tasks": True})
        n = 300
        supportive_count = 0
        for _ in range(n):
            result = generate_nudges(ins, USER_CTX, _history(), _prefs(strictness=0.7))
            for nudge in result:
                if any(kw.lower() in nudge["message"].lower() for kw in supportive_keywords):
                    supportive_count += 1
        self.assertLess(supportive_count, n * 0.5, f"Too many supportive messages: {supportive_count}/{n}")


# ---------------------------------------------------------------------------
# Limits & Suppression — IMPLEMENTATION_GUIDE Step 6
# ---------------------------------------------------------------------------

class TestLimitsAndSuppression(unittest.TestCase):

    def test_daily_limit_blocks_further_nudges(self):
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, USER_CTX, _history(sent=3), _prefs(max_nudges=3))
        self.assertEqual(result, [])

    def test_low_priority_suppressed_on_last_slot(self):
        """Only 1 slot left → low priority (activation) should be suppressed."""
        ins = _insight({"needs_activation": True})
        result = generate_nudges(ins, USER_CTX, _history(sent=2), _prefs(max_nudges=3))
        for nudge in result:
            self.assertNotEqual(nudge["priority"], "low")

    def test_high_priority_still_sent_on_last_slot(self):
        """Only 1 slot left → high priority (correction) should still fire."""
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, USER_CTX, _history(sent=2), _prefs(max_nudges=3))
        self.assertGreater(len(result), 0)

    def test_all_recent_types_deduped_returns_empty(self):
        """If all triggered types are in recent_nudges, return empty."""
        ins = _insight({"has_overdue_tasks": True})
        hist = _history(sent=0, recent_types=["correction"])
        result = generate_nudges(ins, USER_CTX, hist, _prefs())
        self.assertEqual(result, [])

    def test_partial_dedup_returns_remaining(self):
        """If one of two triggered types is in recent_nudges, only the other is returned."""
        ins = _insight({"has_overdue_tasks": True, "goal_at_risk": True})
        hist = _history(sent=0, recent_types=["correction"])
        result = generate_nudges(ins, USER_CTX, hist, _prefs())
        types = [n["type"] for n in result]
        self.assertNotIn("correction", types)
        self.assertIn("strategic", types)


# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------

class TestTimeWindow(unittest.TestCase):

    def test_inside_window_returns_immediate(self):
        ins = _insight({"has_overdue_tasks": True})
        prefs = _prefs(windows=[{"start": "00:00", "end": "23:59"}])
        result = generate_nudges(ins, USER_CTX, _history(), prefs)
        self.assertGreater(len(result), 0)
        for nudge in result:
            self.assertEqual(nudge["timing"], "immediate")

    def test_outside_window_returns_scheduled(self):
        ins = _insight({"has_overdue_tasks": True})
        prefs = _prefs(windows=[{"start": "00:00", "end": "00:01"}])
        result = generate_nudges(ins, USER_CTX, _history(), prefs)
        self.assertGreater(len(result), 0)
        for nudge in result:
            self.assertEqual(nudge["timing"], "scheduled")

    def test_no_windows_treated_as_open(self):
        ins = _insight({"has_overdue_tasks": True})
        prefs = {"max_nudges_per_day": 3, "strictness": 0.7, "allowed_time_windows": []}
        result = generate_nudges(ins, USER_CTX, _history(), prefs)
        self.assertGreater(len(result), 0)
        for nudge in result:
            self.assertEqual(nudge["timing"], "immediate")


# ---------------------------------------------------------------------------
# Input edge cases
# ---------------------------------------------------------------------------

class TestInputEdgeCases(unittest.TestCase):

    def test_user_context_accepted(self):
        ctx = {"active_project": "Sprint A", "mood": "focused", "device": "mobile"}
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, ctx, _history(), _prefs())
        self.assertIsInstance(result, list)

    def test_history_last_nudge_time_accepted(self):
        hist = {
            "nudges_sent_today": 1,
            "last_nudge_time":   "2026-04-05T10:00:00",
            "recent_nudges":     [{"type": "reminder"}],
        }
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, USER_CTX, hist, _prefs())
        self.assertIsInstance(result, list)

    def test_empty_history_defaults_safely(self):
        result = generate_nudges(_insight({"has_overdue_tasks": True}), USER_CTX, {}, _prefs())
        self.assertIsInstance(result, list)

    def test_empty_preferences_uses_defaults(self):
        result = generate_nudges(_insight({"has_overdue_tasks": True}), USER_CTX, _history(), {})
        self.assertIsInstance(result, list)

    def test_max_nudges_per_day_default_is_3(self):
        """With empty prefs, default max_nudges_per_day should be 3 (not 2)."""
        ins = _insight({"has_overdue_tasks": True})
        result = generate_nudges(ins, USER_CTX, _history(sent=2), {})
        self.assertGreater(len(result), 0)


# ---------------------------------------------------------------------------
# WS2: Task-aware message generation
# ---------------------------------------------------------------------------

class TestTaskAwareMessages(unittest.TestCase):

    def _ctx_with_tasks(self, tasks: list) -> dict:
        return {"tasks": tasks}

    def _overdue(self, title: str, nudge_msg: str = None, due_date: str = None) -> dict:
        t = {"title": title, "status": "overdue"}
        if nudge_msg:
            t["nudge_message"] = nudge_msg
        if due_date:
            t["due_date"] = due_date
        return t

    def _pending(self, title: str) -> dict:
        return {"title": title, "status": "pending"}

    # --- _get_task_context unit tests ---

    def test_get_task_context_single_overdue(self):
        ctx = self._ctx_with_tasks([self._overdue("Renew insurance")])
        result = _get_task_context(ctx)
        self.assertEqual(result["overdue_titles"], ["Renew insurance"])
        self.assertEqual(result["overdue_count"], 1)
        self.assertEqual(result["pending_count"], 0)
        self.assertEqual(result["custom_messages"], [])

    def test_get_task_context_custom_message_collected(self):
        ctx = self._ctx_with_tasks([self._overdue("Pay taxes", nudge_msg="Stop avoiding this")])
        result = _get_task_context(ctx)
        self.assertEqual(result["custom_messages"], ["Stop avoiding this"])

    def test_get_task_context_pending_counted(self):
        ctx = self._ctx_with_tasks([
            self._overdue("Task A"),
            self._pending("Task B"),
            self._pending("Task C"),
        ])
        result = _get_task_context(ctx)
        self.assertEqual(result["overdue_count"], 1)
        self.assertEqual(result["pending_count"], 2)

    def test_get_task_context_empty(self):
        result = _get_task_context({})
        self.assertEqual(result["overdue_count"], 0)
        self.assertEqual(result["pending_count"], 0)
        self.assertEqual(result["custom_messages"], [])

    # --- _pick_task_aware_message unit tests ---

    def test_single_overdue_message(self):
        """AC2: single overdue task references its name."""
        ctx = _get_task_context(self._ctx_with_tasks([self._overdue("Renew insurance")]))
        msg = _pick_task_aware_message("correction", ctx, strictness=1.0)
        self.assertIn("Renew insurance", msg)
        self.assertIn("Handle them now", msg)

    def test_custom_nudge_message_preferred(self):
        """AC3: user-written nudge_message is returned verbatim for correction."""
        ctx = _get_task_context(self._ctx_with_tasks([
            self._overdue("Pay taxes", nudge_msg="Stop avoiding this")
        ]))
        msg = _pick_task_aware_message("correction", ctx, strictness=1.0)
        self.assertEqual(msg, "Stop avoiding this")

    def test_three_overdue_tasks_message(self):
        """AC4: 3 overdue tasks → 'Task A and 2 other task(s) are overdue.'"""
        ctx = _get_task_context(self._ctx_with_tasks([
            self._overdue("Task A"),
            self._overdue("Task B"),
            self._overdue("Task C"),
        ]))
        msg = _pick_task_aware_message("correction", ctx, strictness=1.0)
        self.assertIn("Task A", msg)
        self.assertIn("2 other task(s)", msg)

    def test_two_overdue_tasks_message(self):
        """2 overdue tasks → 'X and Y are both overdue.'"""
        ctx = _get_task_context(self._ctx_with_tasks([
            self._overdue("Task A"),
            self._overdue("Task B"),
        ]))
        msg = _pick_task_aware_message("correction", ctx, strictness=1.0)
        self.assertIn("Task A", msg)
        self.assertIn("Task B", msg)
        self.assertIn("both overdue", msg)

    def test_activation_with_pending_count(self):
        """AC5: activation nudge references pending task count."""
        ctx = _get_task_context(self._ctx_with_tasks([
            self._pending("Task 1"),
            self._pending("Task 2"),
            self._pending("Task 3"),
            self._pending("Task 4"),
        ]))
        msg = _pick_task_aware_message("activation", ctx, strictness=1.0)
        self.assertIn("4 pending task(s)", msg)

    def test_fallback_to_generic_when_no_task_context(self):
        """AC7: strategic, reflection, reminder fall back to generic templates."""
        ctx = _get_task_context({})
        for nudge_type in ("strategic", "reflection", "reminder"):
            msg = _pick_task_aware_message(nudge_type, ctx, strictness=0.7)
            self.assertIsInstance(msg, str)
            self.assertGreater(len(msg), 10)

    def test_correction_falls_back_when_no_overdue(self):
        """correction with no overdue tasks falls back to generic template."""
        ctx = _get_task_context({})
        msg = _pick_task_aware_message("correction", ctx, strictness=1.0)
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 10)

    # --- Integration: task-aware messages in generate_nudges ---

    def test_generate_nudges_uses_task_aware_message(self):
        """generate_nudges end-to-end: single overdue task appears in correction message."""
        ins = _insight({"has_overdue_tasks": True})
        ctx = self._ctx_with_tasks([self._overdue("Renew insurance")])
        result = generate_nudges(ins, ctx, _history(), _prefs(strictness=1.0))
        correction = next((n for n in result if n["type"] == "correction"), None)
        self.assertIsNotNone(correction)
        self.assertIn("Renew insurance", correction["message"])

    def test_generate_nudges_custom_message_end_to_end(self):
        """generate_nudges returns user's custom nudge_message for correction."""
        ins = _insight({"has_overdue_tasks": True})
        ctx = self._ctx_with_tasks([self._overdue("Pay taxes", nudge_msg="Stop avoiding this")])
        result = generate_nudges(ins, ctx, _history(), _prefs())
        correction = next((n for n in result if n["type"] == "correction"), None)
        self.assertIsNotNone(correction)
        self.assertEqual(correction["message"], "Stop avoiding this")


# ---------------------------------------------------------------------------
# Performance — TEST_PLAN.md: decision < 50ms
# ---------------------------------------------------------------------------

class TestPerformance(unittest.TestCase):

    def test_decision_under_50ms(self):
        import time
        ins = _insight({"has_overdue_tasks": True, "goal_at_risk": True, "needs_activation": True})
        start = time.perf_counter()
        for _ in range(100):
            generate_nudges(ins, USER_CTX, _history(), _prefs())
        elapsed_ms = (time.perf_counter() - start) * 1000 / 100
        self.assertLess(elapsed_ms, 50, f"Average decision took {elapsed_ms:.2f}ms (limit: 50ms)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
