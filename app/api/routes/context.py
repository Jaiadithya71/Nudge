from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.services.orchestrator_service import get_context

router = APIRouter()


@router.get("/context")
def read_context(user_id: str = Depends(get_current_user)):
    data = get_context(user_id)
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data
