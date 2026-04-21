from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.dependencies import get_current_user
from api.services.task_service import create_goal, update_goal, delete_goal

router = APIRouter()


class CreateGoalRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"


class UpdateGoalRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None


@router.post("/goals", status_code=201)
def create(payload: CreateGoalRequest, user_id: str = Depends(get_current_user)):
    result = create_goal(user_id, payload.model_dump(exclude_none=True))
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.patch("/goals/{goal_id}")
def update(goal_id: str, payload: UpdateGoalRequest, user_id: str = Depends(get_current_user)):
    result = update_goal(user_id, goal_id, payload.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.delete("/goals/{goal_id}", status_code=204)
def delete(goal_id: str, user_id: str = Depends(get_current_user)):
    result = delete_goal(user_id, goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")
