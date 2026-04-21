"""
validator.py — Parse raw LLM output and validate it matches the Insight schema.

Raises ValidationError on any failure; callers use this to trigger retries.
"""

import json
import re
from typing import Any, Dict

from .schemas import REQUIRED_INSIGHT_FIELDS


class ValidationError(Exception):
    """Raised when LLM output cannot be parsed or fails schema validation."""
    pass


def _extract_json(raw: str) -> str:
    """
    Extract a JSON object from a raw string.

    LLMs sometimes wrap JSON in markdown code fences (```json ... ```).
    This strips those fences and returns the bare JSON string.
    """
    # Try to find a JSON block inside markdown fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    # Try to find a bare JSON object
    bare_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if bare_match:
        return bare_match.group(0)

    raise ValidationError(f"No JSON object found in LLM output: {raw!r}")


def parse_and_validate(raw: str) -> Dict[str, Any]:
    """
    Parse *raw* as JSON and validate every required Insight field is present
    and non-empty.

    Args:
        raw: Raw string output from an LLM call.

    Returns:
        A dict that conforms to the Insight schema.

    Raises:
        ValidationError: If parsing fails or required fields are missing/empty.
    """
    json_str = _extract_json(raw)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"JSON parse error: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError(f"Expected a JSON object, got {type(data).__name__}")

    missing = [f for f in REQUIRED_INSIGHT_FIELDS if f not in data]
    if missing:
        raise ValidationError(f"Missing required Insight fields: {missing}")

    empty = [f for f in REQUIRED_INSIGHT_FIELDS if not data[f] and data[f] != 0 and f != "decision_signals"]
    if empty:
        raise ValidationError(f"Empty required Insight fields: {empty}")

    ds = data.get("decision_signals")
    if not isinstance(ds, dict):
        raise ValidationError("decision_signals must be a dictionary")

    required_ds_fields = ["needs_activation", "needs_correction", "goal_at_risk", "has_overdue_tasks"]
    for dsf in required_ds_fields:
        if dsf not in ds:
            raise ValidationError(f"decision_signals missing required field: {dsf}")
        if not isinstance(ds[dsf], bool):
            raise ValidationError(f"decision_signals['{dsf}'] must be a boolean, got {type(ds[dsf]).__name__}")

    return data
