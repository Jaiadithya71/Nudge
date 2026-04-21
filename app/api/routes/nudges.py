from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.services.orchestrator_service import get_nudges

router = APIRouter()


@router.get("/nudges")
def read_nudges(mode: str = "mock", user_id: str = Depends(get_current_user)):
    nudges = get_nudges(user_id, mode)
    return {"nudges": nudges}
