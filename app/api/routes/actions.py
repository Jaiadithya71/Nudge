from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.schemas.base import ActionRequest
from api.services.orchestrator_service import log_action

router = APIRouter()


@router.post("/log-action")
def log_user_action(payload: ActionRequest, user_id: str = Depends(get_current_user)):
    data = log_action(user_id, payload.action, payload.metadata)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data
