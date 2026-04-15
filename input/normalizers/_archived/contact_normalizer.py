"""
contact_normalizer.py - Normalizes Notion contacts to the Memory contacts schema.

Memory ingest("contacts") expects: id, name, email, last_interaction, importance_score
"""

from typing import List, Dict, Any


def normalize_contacts(raw_contacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for c in raw_contacts:
        normalized.append({
            "id":               c.get("contact_id"),
            "name":             c.get("name", "Unknown"),
            "email":            c.get("email"),
            "last_interaction": c.get("last_interaction"),
            "importance_score": c.get("importance_score", 0.3),
        })
    return normalized
