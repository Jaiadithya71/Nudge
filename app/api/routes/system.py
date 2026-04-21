from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.schemas.base import CycleRequest
from api.services.orchestrator_service import run_cycle

router = APIRouter()


@router.post("/run-cycle")
def execute_cycle(payload: CycleRequest, user_id: str = Depends(get_current_user)):
    data = run_cycle(user_id, payload.job_type, payload.mode)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data
