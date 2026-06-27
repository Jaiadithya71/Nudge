"""
server.py — MCP server entrypoint for Nudge Tasks.

Starts an MCP server over stdio, exposes 11 task-management tools, and routes
all reads/writes through the Nudge FastAPI layer via NudgeAPIClient.

Usage:
    python -m mcp_servers.tasks_server.server

Required env vars:
    NUDGE_API_URL  — base URL of the running FastAPI server
    NUDGE_JWT      — pre-obtained JWT for the target user

Optional env vars:
    NUDGE_MCP_TIMEOUT    — HTTP timeout in seconds (default 10.0)
    NUDGE_MCP_LOG_LEVEL  — Python logging level (default INFO)
"""

from __future__ import annotations

import asyncio
import logging
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .api_client import NudgeAPIClient
from .tools import TOOL_DEFINITIONS, dispatch_tool


def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(
            f"Required env var '{name}' is not set. "
            "Set it before starting the server (see README.md)."
        )
    return v


async def main() -> None:
    log_level = os.environ.get("NUDGE_MCP_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    api_url = _require_env("NUDGE_API_URL")
    jwt = _require_env("NUDGE_JWT")
    timeout = float(os.environ.get("NUDGE_MCP_TIMEOUT", "10.0"))

    client = NudgeAPIClient(base_url=api_url, jwt=jwt, timeout=timeout)
    server = Server("nudge-tasks")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.input_schema,
            )
            for t in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        result = await dispatch_tool(name, arguments, client)
        return [types.TextContent(type="text", text=result)]

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
