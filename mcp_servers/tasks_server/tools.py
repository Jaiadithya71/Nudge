"""
tools.py — The 11 MCP tool definitions and their handlers.

Each ToolDef carries:
  - name / description / input_schema for the MCP protocol
  - a handler(arguments, client) -> str coroutine

dispatch_tool() routes by name and returns a JSON string.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from .api_client import NudgeAPIClient, NudgeAPIError

logger = logging.getLogger(__name__)

_CONTEXT_DROP_KEYS = {"contacts", "behavior_patterns", "goal_alignments"}


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def _mcp_error(msg: str) -> str:
    return _json({"error": msg})


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    _handler: Callable[..., Coroutine]

    def mcp_definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    async def handle(self, arguments: dict, client: NudgeAPIClient) -> str:
        try:
            return await self._handler(arguments, client)
        except NudgeAPIError as exc:
            if exc.status == 401:
                return _mcp_error(f"Unauthorised — JWT may be expired. Re-obtain via /api/auth/login.")
            if exc.status == 404:
                return _mcp_error(f"Not found: {exc.endpoint}")
            return _mcp_error(f"API error {exc.status} on {exc.endpoint}: {exc.body[:200]}")
        except Exception as exc:
            logger.exception("[tool:%s] unexpected error", self.name)
            return _mcp_error(f"Unexpected error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def _list_tasks(args: dict, client: NudgeAPIClient) -> str:
    params: dict = {"status": args.get("status", "pending")}
    limit = args.get("limit", 50)
    if limit is not None:
        params["limit"] = min(int(limit), 200)
    try:
        tasks = await client.get("/api/tasks", params=params)
    except NudgeAPIError as exc:
        if exc.status == 404:
            return _json([])
        raise
    return _json(tasks)


async def _get_task(args: dict, client: NudgeAPIClient) -> str:
    task_id = args["task_id"]
    task = await client.get(f"/api/tasks/{task_id}")
    return _json(task)


async def _create_task(args: dict, client: NudgeAPIClient) -> str:
    result = await client.post("/api/tasks", json=args)
    return _json(result)


async def _update_task(args: dict, client: NudgeAPIClient) -> str:
    task_id = args.pop("task_id")
    result = await client.patch(f"/api/tasks/{task_id}", json=args)
    return _json(result)


async def _complete_task(args: dict, client: NudgeAPIClient) -> str:
    task_id = args["task_id"]
    result = await client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
    return _json({
        "task_id": task_id,
        "status": result.get("status", "completed"),
        "completed_at": result.get("last_modified"),
    })


async def _delete_task(args: dict, client: NudgeAPIClient) -> str:
    task_id = args["task_id"]
    await client.delete(f"/api/tasks/{task_id}")
    return _json({"deleted": True, "task_id": task_id})


async def _find_similar_tasks(args: dict, client: NudgeAPIClient) -> str:
    body = {
        "query": args["query"],
        "limit": min(int(args.get("limit", 10)), 50),
    }
    results = await client.post("/api/search/tasks", json=body)
    return _json(results)


async def _get_daily_context(args: dict, client: NudgeAPIClient) -> str:
    ctx = await client.get("/api/context")
    if isinstance(ctx, dict):
        for key in _CONTEXT_DROP_KEYS:
            ctx.pop(key, None)
    return _json(ctx)


async def _tasks_for_goal(args: dict, client: NudgeAPIClient) -> str:
    goal_id = args["goal_id"]
    try:
        tasks = await client.get("/api/tasks", params={"status": "all", "goal_id": goal_id, "limit": 200})
    except NudgeAPIError as exc:
        if exc.status == 404:
            return _json([])
        raise
    return _json(tasks)


async def _list_goals(args: dict, client: NudgeAPIClient) -> str:
    ctx = await client.get("/api/context")
    goals = ctx.get("goals", []) if isinstance(ctx, dict) else []
    trimmed = [
        {k: g[k] for k in ("id", "title", "priority", "description") if k in g}
        for g in goals
    ]
    return _json(trimmed)


async def _log_action(args: dict, client: NudgeAPIClient) -> str:
    action_type = args["action_type"]
    metadata: dict = {}
    if args.get("task_id"):
        metadata["task_id"] = args["task_id"]
    if args.get("notes"):
        metadata["notes"] = args["notes"]
    result = await client.post("/api/log-action", json={"action": action_type, "metadata": metadata})
    return _json({"logged": True, "action_id": result.get("id", "")})


# ─────────────────────────────────────────────────────────────────────────────
# Tool catalog
# ─────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[ToolDef] = [
    ToolDef(
        name="list_tasks",
        description=(
            "List the user's tasks. Filter by status (pending, overdue, completed, or all). "
            "Use this to see what the user is working on right now."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "overdue", "completed", "all"],
                    "description": "Filter tasks by status. Defaults to 'pending'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tasks to return (1-200). Defaults to 50.",
                    "minimum": 1,
                    "maximum": 200,
                },
            },
        },
        _handler=_list_tasks,
    ),
    ToolDef(
        name="get_task",
        description="Fetch a single task with all details including nudge configuration and custom nudge message.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task's unique id."},
            },
            "required": ["task_id"],
        },
        _handler=_get_task,
    ),
    ToolDef(
        name="create_task",
        description=(
            "Create a new task. Provide at minimum a title. Optional: notes, due_date (YYYY-MM-DD), "
            "priority (low/medium/high), goal_id to link to a goal, and nudge configuration "
            "(nudge_enabled, nudge_times as list of HH:MM strings, nudge_days as list of weekday names, "
            "nudge_message as custom reminder text)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title (required)."},
                "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format."},
                "goal_id": {"type": "string", "description": "ID of the goal this task belongs to."},
                "nudge_message": {"type": "string", "description": "Custom reminder text for this task."},
                "nudge_time": {"type": "string", "description": "Legacy single nudge time HH:MM."},
                "nudge_times": {"type": "string", "description": 'JSON array of HH:MM strings e.g. \'["08:00","15:00"]\'.'},
                "nudge_days": {"type": "string", "description": 'JSON array of day abbreviations e.g. \'["mon","wed","fri"]\'.'},
                "nudge_enabled": {"type": "integer", "description": "1 to enable nudges (default), 0 to disable."},
            },
            "required": ["title"],
        },
        _handler=_create_task,
    ),
    ToolDef(
        name="update_task",
        description="Update fields on an existing task. Only pass the fields you want to change.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task's unique id (required)."},
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "overdue", "completed"]},
                "due_date": {"type": "string"},
                "goal_id": {"type": "string"},
                "nudge_message": {"type": "string"},
                "nudge_time": {"type": "string"},
                "nudge_times": {"type": "string"},
                "nudge_days": {"type": "string"},
                "nudge_enabled": {"type": "integer"},
            },
            "required": ["task_id"],
        },
        _handler=_update_task,
    ),
    ToolDef(
        name="complete_task",
        description=(
            "Mark a task as completed. This also triggers nudge re-scheduling and action logging "
            "on the server side."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task's unique id."},
            },
            "required": ["task_id"],
        },
        _handler=_complete_task,
    ),
    ToolDef(
        name="delete_task",
        description=(
            "Permanently delete a task. This cannot be undone. "
            "Prefer complete_task unless the user explicitly wants to remove the task."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task's unique id."},
            },
            "required": ["task_id"],
        },
        _handler=_delete_task,
    ),
    ToolDef(
        name="find_similar_tasks",
        description=(
            "Find tasks semantically similar to a natural-language query. Use this when the user "
            "describes something fuzzy like 'the thing about the insurance' rather than naming the exact task."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language description of the task(s) to find."},
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (1-50). Defaults to 10.",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["query"],
        },
        _handler=_find_similar_tasks,
    ),
    ToolDef(
        name="get_daily_context",
        description=(
            "Return the user's current-day snapshot: goals, today's tasks grouped by status, "
            "today's calendar events, and recent actions. Use this at the start of a conversation "
            "to ground yourself in the user's current state."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        _handler=_get_daily_context,
    ),
    ToolDef(
        name="tasks_for_goal",
        description="List all tasks linked to a specific goal.",
        input_schema={
            "type": "object",
            "properties": {
                "goal_id": {"type": "string", "description": "The goal's unique id."},
            },
            "required": ["goal_id"],
        },
        _handler=_tasks_for_goal,
    ),
    ToolDef(
        name="list_goals",
        description=(
            "List the user's goals. Read-only from this MCP server — "
            "goal editing happens in the dashboard."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        _handler=_list_goals,
    ),
    ToolDef(
        name="log_action",
        description=(
            "Record that the user acknowledged, snoozed, or ignored something. "
            "Call this when the user confirms they took action on a nudge or task via the conversation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["acknowledged", "snoozed", "ignored", "completed"],
                    "description": "What the user did.",
                },
                "task_id": {"type": "string", "description": "Optional task id this action relates to."},
                "notes": {"type": "string", "description": "Optional free-text notes."},
            },
            "required": ["action_type"],
        },
        _handler=_log_action,
    ),
]

_TOOL_MAP: dict[str, ToolDef] = {t.name: t for t in TOOL_DEFINITIONS}


async def dispatch_tool(name: str, arguments: dict, client: NudgeAPIClient) -> str:
    tool = _TOOL_MAP.get(name)
    if tool is None:
        return _mcp_error(f"Unknown tool: {name}")
    return await tool.handle(arguments, client)
