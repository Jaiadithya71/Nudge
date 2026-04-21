"""
test_invalid_json.py — TEST_PLAN § 1: Invalid JSON Handling

Verifies that when the LLM returns bad output, the retry mechanism fires
and ultimately raises a ValidationError after all retries are exhausted.
"""

import pytest
from unittest.mock import patch, MagicMock

from llm_module import generate_insight
from llm_module.validator import ValidationError


_BAD_OUTPUTS = [
    "This is not JSON at all.",
    "```json\n{broken",
    '{"insight_id": "abc"}',          # Missing most fields
    "",                                # Completely empty
    "null",                            # Valid JSON but not an object
]


@pytest.mark.parametrize("bad_output", _BAD_OUTPUTS)
def test_bad_llm_output_raises_validation_error(minimal_context, bad_output):
    """Each bad output should result in a ValidationError after retries."""
    with patch("llm_module.llm_client.call_llm", return_value=bad_output):
        with pytest.raises(ValidationError):
            generate_insight(minimal_context, mode="real")


def test_retry_attempts_on_invalid_json(minimal_context):
    """Confirm that the retry loop fires exactly MAX_RETRIES times."""
    call_count = 0

    def flaky_llm(prompt):
        nonlocal call_count
        call_count += 1
        return "not json"

    with patch("llm_module.llm_client.call_llm", side_effect=flaky_llm):
        with pytest.raises(ValidationError):
            generate_insight(minimal_context, mode="real")

    assert call_count == 3, f"Expected 3 retry attempts, got {call_count}"


def test_retry_succeeds_on_third_attempt(minimal_context):
    """If the LLM returns valid JSON on the 3rd try, the call should succeed."""
    import json

    good_insight = {
        "insight_id": "12345678-1234-4abc-abcd-123456789012",
        "summary": "User shows moderate alignment.",
        "key_observations": ["Consistent morning output."],
        "goal_alignment": "Goals partially addressed.",
        "behavior_flags": ["Context-switching detected."],
        "opportunity_areas": ["Time-blocking recommended."],
    }

    responses = ["bad", "also bad", json.dumps(good_insight)]
    call_count = 0

    def eventually_good(prompt):
        nonlocal call_count
        result = responses[call_count]
        call_count += 1
        return result

    with patch("llm_module.llm_client.call_llm", side_effect=eventually_good):
        result = generate_insight(minimal_context, mode="real")

    assert result["insight_id"] == good_insight["insight_id"]
    assert call_count == 3
