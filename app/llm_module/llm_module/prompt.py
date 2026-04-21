"""
prompt.py — Build the LLM prompt from a UserContext.

Tone: 70% direct/corrective, 30% constructive (per SPEC.md).
Truncates large task lists to respect token limits.
"""

import json
from typing import Any, Dict, List

# Maximum number of tasks to include before truncating
MAX_TASKS = 20

# Maximum number of items per list field
MAX_LIST_ITEMS = 15

_SYSTEM_PROMPT = """\
You are a behavioral analyst and performance coach evaluating a user's productivity and goal alignment.

Your tone must be:
- 70% direct and corrective: call out gaps, missed commitments, and misaligned priorities clearly
- 30% constructive: highlight genuine wins and concrete next steps

You will receive structured data about the user's goals, tasks, recent actions, behavior patterns, \
and a daily summary.

Your output MUST be a single valid JSON object matching this exact schema — no prose, no markdown fences:

{
  "insight_id": "<uuid-v4 string>",
  "summary": "<2-3 sentence high-level assessment>",
  "key_observations": ["<observation>", ...],
  "goal_alignment": "<paragraph evaluating how well the user's actions align with their stated goals>",
  "behavior_flags": ["<flag>", ...],
  "opportunity_areas": ["<opportunity>", ...],
  "decision_signals": {
    "needs_activation": true,
    "needs_correction": false,
    "goal_at_risk": false,
    "has_overdue_tasks": false
  }
}

IMPORTANT INSTRUCTIONS FOR decision_signals:
You MUST populate the `decision_signals` object with explicit boolean values (true or false).
Do NOT omit any field. Do NOT leave any field undefined.
- needs_activation: set to true if there is no recent activity or low engagement.
- needs_correction: set to true if procrastination or delay patterns are identified.
- goal_at_risk: set to true if there is low progress or misalignment with goals.
- has_overdue_tasks: set to true if explicit overdue tasks exist in the task list.

Rules:
- All list fields must have at least one item
- Do not include any text outside the JSON object
- insight_id must be a valid UUID v4
- decision_signals fields must be strictly boolean
"""


def _truncate_list(items: List[Any], max_items: int, label: str) -> List[Any]:
    if len(items) <= max_items:
        return items
    truncated = items[:max_items]
    truncated.append(f"... ({len(items) - max_items} more {label} truncated)")
    return truncated


def build_prompt(context: Dict[str, Any]) -> str:
    """
    Build the full prompt string to send to the LLM.

    Applies truncation to large lists so we stay within reasonable token limits.

    Args:
        context: A dict conforming to the UserContext schema.

    Returns:
        A prompt string (system + user message combined, suitable for Gemini).
    """
    goals = _truncate_list(context.get("goals", []), MAX_LIST_ITEMS, "goals")
    tasks = _truncate_list(context.get("tasks", []), MAX_TASKS, "tasks")
    recent_actions = _truncate_list(
        context.get("recent_actions", []), MAX_LIST_ITEMS, "actions"
    )
    behavior_patterns = _truncate_list(
        context.get("behavior_patterns", []), MAX_LIST_ITEMS, "patterns"
    )
    daily_summary = context.get("daily_summary", "")

    user_block = f"""\
=== USER CONTEXT ===

GOALS:
{json.dumps(goals, indent=2)}

TASKS:
{json.dumps(tasks, indent=2)}

RECENT ACTIONS:
{json.dumps(recent_actions, indent=2)}

BEHAVIOR PATTERNS:
{json.dumps(behavior_patterns, indent=2)}

DAILY SUMMARY:
{daily_summary}

=== END USER CONTEXT ===

Now generate the Insight JSON object:"""

    return f"{_SYSTEM_PROMPT}\n\n{user_block}"
