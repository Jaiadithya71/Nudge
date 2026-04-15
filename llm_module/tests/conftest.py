"""
tests/conftest.py — Shared fixtures for the llm_module test suite.
"""

import pytest
from llm_module.schemas import REQUIRED_CONTEXT_FIELDS, REQUIRED_INSIGHT_FIELDS


@pytest.fixture
def minimal_context():
    """A minimal but fully valid UserContext."""
    return {
        "goals": ["Ship feature X by end of quarter"],
        "tasks": [
            {"id": 1, "name": "Write unit tests", "status": "in_progress"},
            {"id": 2, "name": "Code review PR #42", "status": "done"},
        ],
        "recent_actions": ["Opened IDE", "Committed code", "Attended standup"],
        "behavior_patterns": ["Morning focus block", "Afternoon context-switching"],
        "daily_summary": "Productive morning, scattered afternoon. Two tasks completed.",
    }


@pytest.fixture
def empty_context():
    """A valid UserContext with empty list fields (edge case)."""
    return {
        "goals": [],
        "tasks": [],
        "recent_actions": [],
        "behavior_patterns": [],
        "daily_summary": "",
    }


@pytest.fixture
def large_context():
    """A UserContext with many tasks (truncation edge case)."""
    return {
        "goals": [f"Goal {i}" for i in range(30)],
        "tasks": [
            {"id": i, "name": f"Task {i}", "status": "pending"}
            for i in range(50)
        ],
        "recent_actions": [f"Action {i}" for i in range(25)],
        "behavior_patterns": [f"Pattern {i}" for i in range(20)],
        "daily_summary": "A very busy day with many tasks across multiple domains.",
    }


@pytest.fixture
def required_insight_fields():
    return REQUIRED_INSIGHT_FIELDS
