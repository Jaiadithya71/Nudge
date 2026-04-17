"""Tests for NudgeAPIClient — mocks httpx.AsyncClient."""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_servers.tasks_server.api_client import NudgeAPIClient, NudgeAPIError


def _make_response(status: int, body: dict | str | None = None, is_json: bool = True) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.is_success = 200 <= status < 300
    if body is None:
        resp.json.return_value = {}
        resp.text = ""
    elif isinstance(body, str):
        resp.json.side_effect = Exception("not json")
        resp.text = body
    else:
        resp.json.return_value = body
        resp.text = str(body)
    return resp


@pytest.fixture
def client():
    return NudgeAPIClient(base_url="http://test.local", jwt="test-token", timeout=5.0)


@pytest.mark.asyncio
async def test_jwt_header_injected(client):
    """Every request must carry Authorization: Bearer <jwt>."""
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, {"tasks": []})
        await client.get("/api/tasks")
        assert client._client.headers.get("authorization", "").startswith("Bearer ")


@pytest.mark.asyncio
async def test_get_returns_json(client):
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, [{"id": "1", "title": "Buy milk"}])
        result = await client.get("/api/tasks", params={"status": "pending"})
    assert result == [{"id": "1", "title": "Buy milk"}]


@pytest.mark.asyncio
async def test_post_returns_json(client):
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_response(201, {"id": "abc", "title": "Test"})
        result = await client.post("/api/tasks", json={"title": "Test"})
    assert result["id"] == "abc"


@pytest.mark.asyncio
async def test_patch_returns_json(client):
    with patch.object(client._client, "patch", new_callable=AsyncMock) as mock_patch:
        mock_patch.return_value = _make_response(200, {"id": "abc", "status": "completed"})
        result = await client.patch("/api/tasks/abc", json={"status": "completed"})
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_delete_204_returns_empty_dict(client):
    with patch.object(client._client, "delete", new_callable=AsyncMock) as mock_del:
        mock_del.return_value = _make_response(204)
        result = await client.delete("/api/tasks/abc")
    assert result == {}


@pytest.mark.asyncio
async def test_non_2xx_raises_nudge_api_error(client):
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(404, "Task not found", is_json=False)
        with pytest.raises(NudgeAPIError) as exc_info:
            await client.get("/api/tasks/missing")
    err = exc_info.value
    assert err.status == 404
    assert "GET /api/tasks/missing" in err.endpoint
    assert "Task not found" in err.body


@pytest.mark.asyncio
async def test_401_raises_nudge_api_error(client):
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(401, "Unauthorized", is_json=False)
        with pytest.raises(NudgeAPIError) as exc_info:
            await client.get("/api/tasks")
    assert exc_info.value.status == 401


@pytest.mark.asyncio
async def test_error_message_truncated_at_200_chars(client):
    long_body = "x" * 500
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        resp = _make_response(500, long_body, is_json=False)
        mock_get.return_value = resp
        with pytest.raises(NudgeAPIError) as exc_info:
            await client.get("/api/context")
    assert len(str(exc_info.value)) < 400


@pytest.mark.asyncio
async def test_aclose_delegates_to_httpx(client):
    with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
        await client.aclose()
    mock_close.assert_called_once()
