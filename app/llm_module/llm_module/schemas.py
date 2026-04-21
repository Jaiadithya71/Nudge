"""
schemas.py — TypedDict definitions for UserContext and Insight.

These mirror the contracts in CONTRACT.md exactly.
"""

from typing import Any, Dict, List, TypedDict


class UserContext(TypedDict):
    """Input contract for generate_insight()."""

    goals: List[str]
    tasks: List[Dict[str, Any]]
    recent_actions: List[str]
    behavior_patterns: List[str]
    daily_summary: str


class DecisionSignals(TypedDict):
    needs_activation: bool
    needs_correction: bool
    goal_at_risk: bool
    has_overdue_tasks: bool


class Insight(TypedDict):
    """Output contract guaranteed by generate_insight()."""

    insight_id: str
    summary: str
    key_observations: List[str]
    goal_alignment: str
    behavior_flags: List[str]
    opportunity_areas: List[str]
    decision_signals: DecisionSignals


# Fields that MUST be present in every Insight (used by validator)
REQUIRED_INSIGHT_FIELDS: List[str] = list(Insight.__annotations__.keys())

# Fields that MUST be present in every UserContext (used for input validation)
REQUIRED_CONTEXT_FIELDS: List[str] = list(UserContext.__annotations__.keys())
