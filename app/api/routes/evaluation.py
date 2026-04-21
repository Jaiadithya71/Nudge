from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.services.orchestrator_service import get_evaluation_data

router = APIRouter()


@router.get("/evaluation/today")
def evaluation_today(user_id: str = Depends(get_current_user)):
    """
    Returns today's nudge performance metrics.

    Response shape:
    {
        "nudges_sent":            int,
        "acknowledged":           int,
        "snoozed":                int,
        "ignored":                int,
        "response_rate":          float,   # (ack+snooze+ignore) / nudges_sent
        "ignore_rate":            float,   # ignored / nudges_sent
        "overdue_tasks_before":   int,     # snapshot from morning job
        "overdue_tasks_after":    int,     # current count from DB
        "overdue_delta":          int,     # before - after (positive = tasks resolved)
        "nudge_breakdown":        {type: count}  # by nudge type
    }
    """
    return get_evaluation_data(user_id)
