"""
test_edge_cases.py — TEST_PLAN § 3: Edge Cases

Covers:
- Empty context (no tasks, no goals) → still valid Insight
- Large context (many tasks) → truncation works, call succeeds
"""

import pytest
from llm_module import generate_insight
from llm_module.schemas import REQUIRED_INSIGHT_FIELDS
from llm_module.prompt import build_prompt, MAX_TASKS, MAX_LIST_ITEMS


# ── Empty context ─────────────────────────────────────────────────────────────

def test_empty_context_returns_valid_insight(empty_context, required_insight_fields):
    """Even with no tasks/goals, mock mode should return a fully valid Insight."""
    result = generate_insight(empty_context, mode="mock")
    for field in required_insight_fields:
        assert field in result, f"Missing field in empty-context insight: {field!r}"


def test_empty_context_insight_is_not_empty(empty_context):
    """The Insight returned for an empty context should still have non-trivial content."""
    result = generate_insight(empty_context, mode="mock")
    assert len(result["summary"]) > 0
    assert len(result["insight_id"]) > 0


def test_empty_context_is_deterministic(empty_context):
    """Empty context mock output should still be deterministic."""
    r1 = generate_insight(empty_context, mode="mock")
    r2 = generate_insight(empty_context, mode="mock")
    assert r1 == r2


# ── Large context (truncation) ────────────────────────────────────────────────

def test_large_context_prompt_truncates_tasks(large_context):
    """build_prompt must truncate task lists that exceed MAX_TASKS."""
    import json

    prompt = build_prompt(large_context)

    # Count how many task entries appear in the prompt JSON section
    # We parse the tasks block back out — the simplest heuristic is
    # that the truncation marker string appears in the prompt.
    assert "truncated" in prompt, (
        f"Expected truncation marker in prompt for {len(large_context['tasks'])} tasks"
    )


def test_large_context_mock_returns_valid_insight(large_context, required_insight_fields):
    """Large context should still produce a valid Insight in mock mode."""
    result = generate_insight(large_context, mode="mock")
    for field in required_insight_fields:
        assert field in result, f"Missing field for large context: {field!r}"


def test_large_context_is_deterministic(large_context):
    """Large context mock output should be deterministic."""
    r1 = generate_insight(large_context, mode="mock")
    r2 = generate_insight(large_context, mode="mock")
    assert r1 == r2
