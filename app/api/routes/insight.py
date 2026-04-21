from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.services.orchestrator_service import get_insight

router = APIRouter()


@router.get("/insight")
def read_insight(mode: str = "mock", user_id: str = Depends(get_current_user)):
    data = get_insight(user_id, mode)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data
