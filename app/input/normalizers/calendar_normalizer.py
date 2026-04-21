"""
calendar_normalizer.py - Normalizes incoming calendar payload to Memory event format.
"""

from typing import List, Dict, Any

def normalize_events(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for e in raw_events:
        normalized.append({
            "id": e.get("id"),
            "title": e.get("title", "Untitled Event"),
            "start_time": e.get("start"),
            "end_time": e.get("end"),
            # In the future, we can add participants/location natively to the Memory schema,
            # or shove them into a metadata/description column.
        })
    return normalized
