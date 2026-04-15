"""
task_normalizer.py - Normalizes incoming tasks payload to Memory task format.
"""

from typing import List, Dict, Any

def normalize_tasks(raw_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for t in raw_tasks:
        normalized.append({
            "id": t.get("task_id"),
            "title": t.get("title", "Untitled Task"),
            "status": t.get("status", "pending"),
            "due_date": t.get("due_date"),
        })
    return normalized
