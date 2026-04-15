"""
goal_normalizer.py - Normalizes Notion goals to the Memory goals schema.

Memory ingest("goals") expects: id, title, description, priority, created_at
"""

from typing import List, Dict, Any


def normalize_goals(raw_goals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for g in raw_goals:
        normalized.append({
            "id":          g.get("goal_id"),
            "title":       g.get("title", "Untitled Goal"),
            "description": g.get("description"),
            "priority":    g.get("priority", "medium"),
        })
    return normalized
