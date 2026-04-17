"""Tests for schema_utils.clean_schema_for_gemini."""

from __future__ import annotations

from mcp_servers.tasks_server.schema_utils import clean_schema_for_gemini, UNSUPPORTED_SCHEMA_KEYS


def test_strips_all_five_offending_keys_at_root():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema",
        "$id": "some-id",
        "definitions": {"MyDef": {"type": "string"}},
        "additionalProperties": False,
        "default": "pending",
        "type": "object",
        "properties": {"status": {"type": "string"}},
    }
    result = clean_schema_for_gemini(schema)
    for key in UNSUPPORTED_SCHEMA_KEYS:
        assert key not in result, f"{key!r} should have been stripped"


def test_preserves_valid_keys():
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
        },
        "required": ["title"],
        "description": "A task",
    }
    result = clean_schema_for_gemini(schema)
    assert result["type"] == "object"
    assert result["required"] == ["title"]
    assert result["description"] == "A task"


def test_strips_offending_keys_in_nested_properties():
    schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "default": "pending",
                "additionalProperties": False,
                "description": "Task status",
            }
        },
    }
    result = clean_schema_for_gemini(schema)
    status_schema = result["properties"]["status"]
    assert "default" not in status_schema
    assert "additionalProperties" not in status_schema
    assert status_schema["description"] == "Task status"


def test_strips_offending_keys_in_items():
    schema = {
        "type": "array",
        "items": {
            "type": "string",
            "default": "x",
            "$schema": "draft-07",
        },
    }
    result = clean_schema_for_gemini(schema)
    assert "default" not in result["items"]
    assert "$schema" not in result["items"]
    assert result["items"]["type"] == "string"


def test_strips_offending_keys_in_oneof():
    schema = {
        "oneOf": [
            {"type": "string", "default": "a"},
            {"type": "null", "additionalProperties": False},
        ]
    }
    result = clean_schema_for_gemini(schema)
    assert "default" not in result["oneOf"][0]
    assert "additionalProperties" not in result["oneOf"][1]


def test_strips_offending_keys_in_anyof():
    schema = {
        "anyOf": [
            {"type": "string", "$id": "foo"},
            {"type": "integer"},
        ]
    }
    result = clean_schema_for_gemini(schema)
    assert "$id" not in result["anyOf"][0]


def test_non_dict_passthrough():
    assert clean_schema_for_gemini("not a dict") == "not a dict"
    assert clean_schema_for_gemini(42) == 42
    assert clean_schema_for_gemini(None) is None


def test_empty_schema_unchanged():
    assert clean_schema_for_gemini({}) == {}


def test_idempotent():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "x": {"type": "string", "default": "y"},
        },
    }
    once = clean_schema_for_gemini(schema)
    twice = clean_schema_for_gemini(once)
    assert once == twice
