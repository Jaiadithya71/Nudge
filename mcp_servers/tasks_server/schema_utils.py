"""
schema_utils.py — JSON Schema cleaner for LLM function-calling consumers.

Claude accepts standard JSON Schema directly. Gemini and some other providers
reject certain schema keys. The cleaner strips those keys so the same tool
definitions can be reused across providers.
"""

from __future__ import annotations

UNSUPPORTED_SCHEMA_KEYS = {"additionalProperties", "$schema", "$id", "definitions", "default"}


def clean_schema_for_gemini(schema: dict) -> dict:
    """Recursively strip JSON Schema keys Gemini rejects.

    Safe no-op for Claude. Covers nested properties, items, oneOf/anyOf.
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for key, value in schema.items():
        if key in UNSUPPORTED_SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            result[key] = {
                prop_name: clean_schema_for_gemini(prop_schema)
                for prop_name, prop_schema in value.items()
            }
        elif key == "items" and isinstance(value, dict):
            result[key] = clean_schema_for_gemini(value)
        elif key in ("oneOf", "anyOf", "allOf") and isinstance(value, list):
            result[key] = [clean_schema_for_gemini(s) for s in value]
        else:
            result[key] = value

    return result
