"""
task_service.py — Write operations for tasks and goals.

SQLite is the sole source of truth. Tasks and goals are managed here only.
Notion write-back is archived in output/_archived/notion_writer.py.
"""

import logging

import api.dependencies  # noqa: F401 — ensures sys.path patched
import memory as mem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def create_task(user_id: str, payload: dict) -> dict:
    try:
        task = mem.create_task(user_id, payload)
        logger.info("[task] Created: user=%s id=%s title=%r", user_id, task["id"], task.get("title"))
        return task
    except Exception as e:
        logger.error("[task] Create failed: user=%s error=%s", user_id, e)
        return {"error": str(e)}


def update_task(user_id: str, task_id: str, updates: dict) -> dict | None:
    try:
        task = mem.update_task(user_id, task_id, updates)
        if task:
            logger.info("[task] Updated: user=%s id=%s fields=%s", user_id, task_id, list(updates))
        return task
    except Exception as e:
        logger.error("[task] Update failed: user=%s id=%s error=%s", user_id, task_id, e)
        return {"error": str(e)}


def delete_task(user_id: str, task_id: str) -> bool:
    try:
        deleted = mem.delete_task(user_id, task_id)
        if deleted:
            logger.info("[task] Deleted: user=%s id=%s", user_id, task_id)
        return deleted
    except Exception as e:
        logger.error("[task] Delete failed: user=%s id=%s error=%s", user_id, task_id, e)
        return False


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def create_goal(user_id: str, payload: dict) -> dict:
    try:
        goal = mem.create_goal(user_id, payload)
        logger.info("[goal] Created: user=%s id=%s title=%r", user_id, goal["id"], goal.get("title"))
        return goal
    except Exception as e:
        logger.error("[goal] Create failed: user=%s error=%s", user_id, e)
        return {"error": str(e)}


def delete_goal(user_id: str, goal_id: str) -> bool:
    try:
        deleted = mem.delete_goal(user_id, goal_id)
        if deleted:
            logger.info("[goal] Deleted: user=%s id=%s", user_id, goal_id)
        return deleted
    except Exception as e:
        logger.error("[goal] Delete failed: user=%s id=%s error=%s", user_id, goal_id, e)
        return False


def update_goal(user_id: str, goal_id: str, updates: dict) -> dict | None:
    try:
        goal = mem.update_goal(user_id, goal_id, updates)
        if goal:
            logger.info("[goal] Updated: user=%s id=%s fields=%s", user_id, goal_id, list(updates))
        return goal
    except Exception as e:
        logger.error("[goal] Update failed: user=%s id=%s error=%s", user_id, goal_id, e)
        return {"error": str(e)}
