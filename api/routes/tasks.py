from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Literal

import api.dependencies  # noqa: F401 — ensures sys.path patched
import memory as mem

from api.dependencies import get_current_user
from api.services.task_service import create_task, update_task, delete_task

router = APIRouter()


class CreateTaskRequest(BaseModel):
    title: str
    due_date: Optional[str] = None
    goal_id: Optional[str] = None
    nudge_message: Optional[str] = None
    nudge_time: Optional[str] = None        # legacy single HH:MM
    nudge_times: Optional[str] = None       # JSON array of HH:MM e.g. '["08:00","15:00"]'
    nudge_days: Optional[str] = None        # JSON array of day abbrevs e.g. '["mon","wed","fri"]'
    nudge_enabled: Optional[int] = 1


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    goal_id: Optional[str] = None
    nudge_message: Optional[str] = None
    nudge_time: Optional[str] = None        # legacy single HH:MM
    nudge_times: Optional[str] = None       # JSON array of HH:MM
    nudge_days: Optional[str] = None        # JSON array of day abbrevs
    nudge_enabled: Optional[int] = None     # 1 = enabled, 0 = disabled


@router.get("/tasks")
def list_tasks_route(
    status: Optional[Literal["pending", "overdue", "completed", "all"]] = "pending",
    limit: int = Query(50, ge=1, le=200),
    goal_id: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    """Return tasks filtered by status (and optionally goal_id) for the authenticated user."""
    return mem.list_tasks(user_id, status=status, limit=limit, goal_id=goal_id)


@router.get("/tasks/{task_id}")
def get_task_route(task_id: str, user_id: str = Depends(get_current_user)):
    """Fetch a single task with all details."""
    task = mem.get_task(user_id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks", status_code=201)
def create(payload: CreateTaskRequest, user_id: str = Depends(get_current_user)):
    result = create_task(user_id, payload.model_dump(exclude_none=True))
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.patch("/tasks/{task_id}")
def update(task_id: str, payload: UpdateTaskRequest, user_id: str = Depends(get_current_user)):
    result = update_task(user_id, task_id, payload.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.delete("/tasks/{task_id}", status_code=204)
def delete(task_id: str, user_id: str = Depends(get_current_user)):
    result = delete_task(user_id, task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
