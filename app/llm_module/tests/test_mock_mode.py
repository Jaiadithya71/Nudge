"""
test_mock_mode.py — TEST_PLAN § 2: Mock Mode Tests

Verifies that mock mode is:
- deterministic: same input → same output
- isolated: no network calls are made
- structurally valid: output matches Insight schema
"""

import pytest
from llm_module import generate_insight
from llm_module.schemas import REQUIRED_INSIGHT_FIELDS


def test_mock_returns_valid_insight(minimal_context, required_insight_fields):
    """Mock output should pass full schema validation."""
    result = generate_insight(minimal_context, mode="mock")
    for field in required_insight_fields:
        assert field in result, f"Mock output missing field: {field!r}"


def test_mock_is_deterministic(minimal_context):
    """Same context → identical output on every call."""
    result_1 = generate_insight(minimal_context, mode="mock")
    result_2 = generate_insight(minimal_context, mode="mock")
    assert result_1 == result_2, "Mock mode must be deterministic"


def test_mock_different_inputs_different_ids(minimal_context):
    """Different contexts should produce different insight_ids."""
    ctx_a = {**minimal_context, "daily_summary": "Productive day."}
    ctx_b = {**minimal_context, "daily_summary": "Completely different summary."}
    result_a = generate_insight(ctx_a, mode="mock")
    result_b = generate_insight(ctx_b, mode="mock")
    assert result_a["insight_id"] != result_b["insight_id"]


def test_mock_mode_makes_no_network_calls(minimal_context, monkeypatch):
    """Mock mode must never import or call the real LLM client."""
    import llm_module

    def fail_if_called(*args, **kwargs):
        raise AssertionError("llm_client.call_llm was called in mock mode!")

    # Patch at the module level in case it's already imported
    monkeypatch.setattr("llm_module.llm_client.call_llm", fail_if_called, raising=False)

    # This should complete without hitting the real client
    result = generate_insight(minimal_context, mode="mock")
    assert result is not None


def test_invalid_mode_raises_value_error(minimal_context):
    """An unrecognised mode should raise ValueError immediately."""
    with pytest.raises(ValueError, match="Invalid mode"):
        generate_insight(minimal_context, mode="hallucinate")
