from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from api.dependencies import get_current_user
import api.dependencies  # noqa: F401
import memory as mem

router = APIRouter()


class PreferencesUpdate(BaseModel):
    morning_time:       Optional[str]   = Field(None, example="07:00")
    midday_time:        Optional[str]   = Field(None, example="12:00")
    evening_time:       Optional[str]   = Field(None, example="19:00")
    max_nudges_per_day: Optional[int]   = Field(None, ge=1, le=20)
    min_gap_hours:      Optional[float] = Field(None, ge=0, le=24)
    strictness:         Optional[float] = Field(None, ge=0.0, le=1.0)


@router.get("/preferences")
def get_preferences(user_id: str = Depends(get_current_user)):
    try:
        return mem.get_preferences(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preferences")
def save_preferences(payload: PreferencesUpdate, user_id: str = Depends(get_current_user)):
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided")
    try:
        return mem.save_preferences(user_id, updates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
