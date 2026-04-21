"""
mock_client.py — Deterministic mock LLM client for testing.

Same input context always produces the same Insight output.
No network calls are made.
"""

import hashlib
import json
import uuid
from typing import Any, Dict


def _stable_uuid(seed: str) -> str:
    """Generate a deterministic UUID v4-shaped string from a seed."""
    # Use first 32 hex chars of sha256 hash, formatted as UUID
    h = hashlib.sha256(seed.encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-4{h[13:16]}-{h[16:20]}-{h[20:32]}"


def call_mock(context: Dict[str, Any]) -> str:
    """
    Return a deterministic Insight JSON string based on the input context.

    The output is seeded from a sha256 hash of the serialised context, so:
    - Same input  → same output (required for mock-mode tests)
    - Different inputs → different insight_ids / content

    Args:
        context: A dict conforming to the UserContext schema.

    Returns:
        A raw JSON string matching the Insight schema.
    """
    seed = json.dumps(context, sort_keys=True, default=str)
    context_hash = hashlib.sha256(seed.encode()).hexdigest()

    goals = context.get("goals", [])
    tasks = context.get("tasks", [])
    behavior_patterns = context.get("behavior_patterns", [])

    # Derive simple deterministic content from the hash
    insight_id = _stable_uuid(context_hash)

    n_tasks = len(tasks)
    n_goals = len(goals)

    summary = (
        f"The user has {n_goals} active goal(s) and {n_tasks} task(s) on record. "
        "Current activity levels suggest moderate engagement. "
        "Alignment with stated priorities requires closer attention."
    )

    key_observations = [
        f"Tracked {n_tasks} task(s) in the current period.",
        f"Identified {len(behavior_patterns)} behaviour pattern(s).",
        "Consistency in daily execution is below optimal threshold." if n_tasks < 3
        else "Task volume is adequate — quality of completion needs review.",
    ]

    goal_alignment = (
        f"With {n_goals} stated goal(s), the user's recent actions show partial alignment. "
        "Key priorities are represented in the task list, but follow-through requires improvement."
        if n_goals > 0
        else "No goals have been set. Establishing clear objectives is the immediate priority."
    )

    behavior_flags = [
        "overdue_task" if any(t.get("status") == "overdue" for t in tasks) else "low_completion_rate",
        "repeated_delay" if len(behavior_patterns) > 0 else "inactivity",
    ]

    opportunity_areas = [
        "Introduce time-blocking for deep work.",
        "Align daily task selection directly with top-priority goals.",
        "Review and prune low-value recurring activities.",
    ]

    has_overdue = any(t.get("status") == "overdue" for t in tasks)
    decision_signals = {
        "needs_activation": len(tasks) == 0, # Low activity roughly equals no tasks here for mock
        "needs_correction": has_overdue or len(behavior_patterns) > 0,
        "goal_at_risk": n_goals > 0 and len(tasks) < 2,
        "has_overdue_tasks": has_overdue
    }

    insight = {
        "insight_id": insight_id,
        "summary": summary,
        "key_observations": key_observations,
        "goal_alignment": goal_alignment,
        "behavior_flags": behavior_flags,
        "opportunity_areas": opportunity_areas,
        "decision_signals": decision_signals,
    }

    return json.dumps(insight)
