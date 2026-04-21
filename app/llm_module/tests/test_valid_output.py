"""
test_valid_output.py — TEST_PLAN § 1: Valid Output

Verifies that a valid UserContext produces an Insight that:
- is a dict
- contains all required fields
- has non-empty values for every field
"""

import pytest
from llm_module import generate_insight
from llm_module.schemas import REQUIRED_INSIGHT_FIELDS


def test_valid_output_returns_dict(minimal_context):
    result = generate_insight(minimal_context, mode="mock")
    assert isinstance(result, dict), "generate_insight should return a dict"


def test_valid_output_all_fields_present(minimal_context, required_insight_fields):
    result = generate_insight(minimal_context, mode="mock")
    for field in required_insight_fields:
        assert field in result, f"Missing required field: {field!r}"


def test_valid_output_no_empty_fields(minimal_context, required_insight_fields):
    result = generate_insight(minimal_context, mode="mock")
    for field in required_insight_fields:
        assert result[field], f"Field {field!r} is empty"


def test_insight_id_is_string(minimal_context):
    result = generate_insight(minimal_context, mode="mock")
    assert isinstance(result["insight_id"], str)
    assert len(result["insight_id"]) > 0


def test_list_fields_are_lists(minimal_context):
    result = generate_insight(minimal_context, mode="mock")
    for field in ("key_observations", "behavior_flags", "opportunity_areas"):
        assert isinstance(result[field], list), f"{field!r} should be a list"
        assert len(result[field]) > 0, f"{field!r} list should not be empty"


def test_string_fields_are_strings(minimal_context):
    result = generate_insight(minimal_context, mode="mock")
    for field in ("insight_id", "summary", "goal_alignment"):
        assert isinstance(result[field], str), f"{field!r} should be a string"
