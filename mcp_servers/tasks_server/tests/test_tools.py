"""Tests for tools.py — mocks NudgeAPIClient, verifies each tool hits the right endpoint."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp_servers.tasks_server.api_client import NudgeAPIError
from mcp_servers.tasks_server.tools import dispatch_tool, TOOL_DEFINITIONS


@pytest.fixture
def client():
    c = MagicMock()
    c.get = AsyncMock()
    c.post = AsyncMock()
    c.patch = AsyncMock()
    c.delete = AsyncMock()
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

async def _dispatch(name: str, args: dict, client) -> dict:
    raw = await dispatch_tool(name, args, client)
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Catalog sanity
# ─────────────────────────────────────────────────────────────────────────────

def test_exactly_11_tools():
    assert len(TOOL_DEFINITIONS) == 11


def test_all_tool_names_unique():
    names = [t.name for t in TOOL_DEFINITIONS]
    assert len(names) == len(set(names))


def test_mcp_definition_has_required_keys():
    for tool in TOOL_DEFINITIONS:
        defn = tool.mcp_definition()
        assert "name" in defn
        assert "description" in defn
        assert "inputSchema" in defn


# ─────────────────────────────────────────────────────────────────────────────
# CRUD tools
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_tasks_calls_get_tasks(client):
    client.get.return_value = [{"id": "1", "title": "Buy milk", "status": "pending"}]
    result = await _dispatch("list_tasks", {"status": "pending", "limit": 10}, client)
    client.get.assert_called_once_with("/api/tasks", params={"status": "pending", "limit": 10})
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_tasks_default_status(client):
    client.get.return_value = []
    await dispatch_tool("list_tasks", {}, client)
    call_kwargs = client.get.call_args
    assert call_kwargs[1]["params"]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task_calls_correct_endpoint(client):
    client.get.return_value = {"id": "abc", "title": "Fix bug", "status": "pending"}
    result = await _dispatch("get_task", {"task_id": "abc"}, client)
    client.get.assert_called_once_with("/api/tasks/abc")
    assert result["id"] == "abc"


@pytest.mark.asyncio
async def test_create_task_posts_to_tasks(client):
    payload = {"title": "New task", "due_date": "2026-05-01"}
    client.post.return_value = {"id": "xyz", **payload}
    result = await _dispatch("create_task", payload, client)
    client.post.assert_called_once_with("/api/tasks", json=payload)
    assert result["id"] == "xyz"


@pytest.mark.asyncio
async def test_update_task_patches_correct_endpoint(client):
    client.patch.return_value = {"id": "abc", "title": "Updated", "status": "pending"}
    result = await _dispatch("update_task", {"task_id": "abc", "title": "Updated"}, client)
    client.patch.assert_called_once_with("/api/tasks/abc", json={"title": "Updated"})
    assert result["title"] == "Updated"


@pytest.mark.asyncio
async def test_complete_task_patches_status_completed(client):
    client.patch.return_value = {"id": "abc", "status": "completed", "last_modified": "2026-04-17T10:00:00"}
    result = await _dispatch("complete_task", {"task_id": "abc"}, client)
    client.patch.assert_called_once_with("/api/tasks/abc", json={"status": "completed"})
    assert result["status"] == "completed"
    assert result["task_id"] == "abc"


@pytest.mark.asyncio
async def test_delete_task_calls_delete_endpoint(client):
    client.delete.return_value = {}
    result = await _dispatch("delete_task", {"task_id": "abc"}, client)
    client.delete.assert_called_once_with("/api/tasks/abc")
    assert result == {"deleted": True, "task_id": "abc"}


# ─────────────────────────────────────────────────────────────────────────────
# Context / semantic tools
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_similar_tasks_posts_to_search(client):
    client.post.return_value = [{"task_id": "1", "title": "Insurance docs", "score": 0.9, "snippet": "TASKS | Insurance"}]
    result = await _dispatch("find_similar_tasks", {"query": "insurance", "limit": 5}, client)
    client.post.assert_called_once_with("/api/search/tasks", json={"query": "insurance", "limit": 5})
    assert result[0]["task_id"] == "1"


@pytest.mark.asyncio
async def test_get_daily_context_strips_unwanted_keys(client):
    client.get.return_value = {
        "user_id": "jai",
        "tasks": [],
        "goals": [],
        "contacts": [{"name": "Alice"}],
        "behavior_patterns": [{"type": "x"}],
        "goal_alignments": [{"score": 0.9}],
        "events": [],
    }
    result = await _dispatch("get_daily_context", {}, client)
    assert "contacts" not in result
    assert "behavior_patterns" not in result
    assert "goal_alignments" not in result
    assert "tasks" in result
    assert "goals" in result


@pytest.mark.asyncio
async def test_tasks_for_goal_filters_by_goal_id(client):
    client.get.return_value = [{"id": "1", "goal_id": "g1"}]
    result = await _dispatch("tasks_for_goal", {"goal_id": "g1"}, client)
    client.get.assert_called_once_with("/api/tasks", params={"status": "all", "goal_id": "g1", "limit": 200})
    assert result[0]["goal_id"] == "g1"


# ─────────────────────────────────────────────────────────────────────────────
# Read-only goals
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_goals_extracts_from_context(client):
    client.get.return_value = {
        "goals": [{"id": "g1", "title": "Get fit", "priority": "high", "description": "Run 5k"}],
        "tasks": [],
    }
    result = await _dispatch("list_goals", {}, client)
    client.get.assert_called_once_with("/api/context")
    assert result[0]["title"] == "Get fit"
    assert "tasks" not in result[0]


# ─────────────────────────────────────────────────────────────────────────────
# Action logging
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_action_maps_action_type_to_action_field(client):
    client.post.return_value = {"id": "act-1", "status": "success"}
    result = await _dispatch("log_action", {"action_type": "acknowledged", "task_id": "abc", "notes": "done"}, client)
    client.post.assert_called_once_with(
        "/api/log-action",
        json={"action": "acknowledged", "metadata": {"task_id": "abc", "notes": "done"}},
    )
    assert result["logged"] is True


@pytest.mark.asyncio
async def test_log_action_minimal_payload(client):
    client.post.return_value = {"status": "success"}
    await dispatch_tool("log_action", {"action_type": "snoozed"}, client)
    call_json = client.post.call_args[1]["json"]
    assert call_json["action"] == "snoozed"
    assert call_json["metadata"] == {}


# ─────────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_404_returns_mcp_error_not_exception(client):
    client.get.side_effect = NudgeAPIError(404, "GET /api/tasks/missing", "not found")
    result = await _dispatch("get_task", {"task_id": "missing"}, client)
    assert "error" in result


@pytest.mark.asyncio
async def test_401_returns_auth_hint(client):
    client.get.side_effect = NudgeAPIError(401, "GET /api/tasks", "unauthorized")
    raw = await dispatch_tool("list_tasks", {}, client)
    assert "JWT" in raw or "Unauthorised" in raw


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client):
    result = await _dispatch("nonexistent_tool", {}, client)
    assert "error" in result


@pytest.mark.asyncio
async def test_list_tasks_404_returns_empty_list(client):
    client.get.side_effect = NudgeAPIError(404, "GET /api/tasks", "not found")
    result = await _dispatch("list_tasks", {"status": "pending"}, client)
    assert result == []
