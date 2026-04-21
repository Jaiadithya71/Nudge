"""
test_missing_fields.py — TEST_PLAN § 1: Missing Fields

Verifies that:
- Missing UserContext fields raise ValueError before any LLM call
- An LLM response missing Insight fields raises ValidationError
"""

import json
import pytest
from unittest.mock import patch

from llm_module import generate_insight
from llm_module.schemas import REQUIRED_CONTEXT_FIELDS, REQUIRED_INSIGHT_FIELDS
from llm_module.validator import ValidationError, parse_and_validate


# ── Input contract tests ─────────────────────────────────────────────────────

@pytest.mark.parametrize("missing_field", REQUIRED_CONTEXT_FIELDS)
def test_missing_context_field_raises_value_error(minimal_context, missing_field):
    """Removing any UserContext field should raise ValueError."""
    bad_context = {k: v for k, v in minimal_context.items() if k != missing_field}
    with pytest.raises(ValueError, match=missing_field):
        generate_insight(bad_context, mode="mock")


def test_empty_context_dict_raises_value_error():
    """A completely empty dict should raise ValueError."""
    with pytest.raises(ValueError):
        generate_insight({}, mode="mock")


# ── Output contract tests ─────────────────────────────────────────────────────

_FULL_VALID_INSIGHT = {
    "insight_id": "12345678-1234-4abc-abcd-123456789012",
    "summary": "Test summary.",
    "key_observations": ["Observation one."],
    "goal_alignment": "Goals are partially aligned.",
    "behavior_flags": ["Flag one."],
    "opportunity_areas": ["Opportunity one."],
}


@pytest.mark.parametrize("missing_field", REQUIRED_INSIGHT_FIELDS)
def test_missing_insight_field_raises_validation_error(missing_field):
    """Removing any Insight field from LLM output should raise ValidationError."""
    bad_output = {k: v for k, v in _FULL_VALID_INSIGHT.items() if k != missing_field}
    with pytest.raises(ValidationError, match=missing_field):
        parse_and_validate(json.dumps(bad_output))


@pytest.mark.parametrize("empty_value", [[], "", None])
def test_empty_insight_field_raises_validation_error(empty_value):
    """An empty required field should fail validation."""
    bad_output = {**_FULL_VALID_INSIGHT, "summary": empty_value}
    with pytest.raises(ValidationError):
        parse_and_validate(json.dumps(bad_output))
