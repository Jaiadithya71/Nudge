"""
api_client.py — Async HTTP wrapper around the Nudge FastAPI server.

One shared httpx.AsyncClient per process lifetime. Adds Bearer JWT to every
request. No retries — if the JWT is expired the caller needs to know.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NudgeAPIError(Exception):
    def __init__(self, status: int, endpoint: str, body: str):
        self.status = status
        self.endpoint = endpoint
        self.body = body
        super().__init__(f"{endpoint} -> {status}: {body[:200]}")


class NudgeAPIClient:
    def __init__(self, base_url: str, jwt: str, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=timeout,
        )

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _check(self, response: httpx.Response, endpoint: str) -> Any:
        if response.is_success:
            if response.status_code == 204:
                return {}
            return response.json()
        body = response.text
        logger.warning("[api] %s -> %d: %s", endpoint, response.status_code, body[:200])
        raise NudgeAPIError(response.status_code, endpoint, body)

    async def get(self, path: str, params: dict | None = None) -> Any:
        url = self._url(path)
        logger.debug("[api] GET %s params=%s", url, params)
        r = await self._client.get(url, params=params)
        return self._check(r, f"GET {path}")

    async def post(self, path: str, json: dict) -> Any:
        url = self._url(path)
        logger.debug("[api] POST %s body=%s", url, json)
        r = await self._client.post(url, json=json)
        return self._check(r, f"POST {path}")

    async def patch(self, path: str, json: dict) -> Any:
        url = self._url(path)
        logger.debug("[api] PATCH %s body=%s", url, json)
        r = await self._client.patch(url, json=json)
        return self._check(r, f"PATCH {path}")

    async def delete(self, path: str) -> Any:
        url = self._url(path)
        logger.debug("[api] DELETE %s", url)
        r = await self._client.delete(url)
        return self._check(r, f"DELETE {path}")

    async def aclose(self) -> None:
        await self._client.aclose()
