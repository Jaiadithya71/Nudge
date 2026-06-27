"""
__init__.py — Public API for the llm_module package.

Usage:
    from llm_module import generate_insight

    insight = generate_insight(context, mode="real")   # calls Gemini 2.5
    insight = generate_insight(context, mode="mock")   # deterministic, no API call
"""

import time

from .mock_client import call_mock
from .prompt import build_prompt
from .schemas import REQUIRED_CONTEXT_FIELDS, Insight, UserContext
from .validator import ValidationError, parse_and_validate

_MAX_RETRIES = 3
_RETRY_DELAYS = [5, 15]  # seconds to wait before attempt 2, then attempt 3

def __safe_fallback_insight() -> dict:
    import uuid
    return {
        "insight_id": str(uuid.uuid4()),
        "summary": "Fallback insight generated due to LLM validation failure.",
        "key_observations": ["LLM failed to produce valid structure"],
        "goal_alignment": "Unknown due to validation failure",
        "behavior_flags": [],
        "opportunity_areas": ["System recovery"],
        "decision_signals": {
            "needs_activation": False,
            "needs_correction": False,
            "goal_at_risk": False,
            "has_overdue_tasks": False
        }
    }


def generate_insight(context: dict, mode: str = "real") -> dict:
    """
    Convert a UserContext dict into a validated Insight dict.

    Args:
        context: Must match the UserContext schema (see schemas.py / CONTRACT.md).
        mode:    "real"  — calls Gemini 2.5 Pro (requires GEMINI_API_KEY in .env)
                 "mock"  — returns deterministic output, no network call

    Returns:
        A dict conforming to the Insight schema.

    Raises:
        ValueError:         If *mode* is invalid or *context* is missing required fields.
        EnvironmentError:   If GEMINI_API_KEY is not set (real mode only).
    """
    if mode not in ("real", "mock"):
        raise ValueError(f"Invalid mode {mode!r}. Must be 'real' or 'mock'.")

    _validate_context(context)

    if mode == "mock":
        try:
            raw = call_mock(context)
            return parse_and_validate(raw)
        except ValidationError:
            return __safe_fallback_insight()

    # Real mode — import lazily so missing API key doesn't break mock usage
    from .llm_client import call_llm

    prompt = build_prompt(context)
    last_error: Exception = ValidationError("No attempts made")

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            raw = call_llm(prompt)
            return parse_and_validate(raw)
        except ValidationError as exc:
            last_error = exc
            print(f"[llm_module] Attempt {attempt}/{_MAX_RETRIES} failed validation: {exc}")
        except Exception as exc:
            last_error = ValidationError(str(exc))
            print(f"[llm_module] Attempt {attempt}/{_MAX_RETRIES} API error: {exc}")

        if attempt < _MAX_RETRIES:
            delay = _RETRY_DELAYS[attempt - 1]
            print(f"[llm_module] Retrying in {delay}s...")
            time.sleep(delay)

    print(f"[llm_module] Returning fallback insight. Last error: {last_error}")
    return __safe_fallback_insight()


def _validate_context(context: dict) -> None:
    """Raise ValueError if any required UserContext fields are missing."""
    missing = [f for f in REQUIRED_CONTEXT_FIELDS if f not in context]
    if missing:
        raise ValueError(
            f"context is missing required UserContext fields: {missing}"
        )
