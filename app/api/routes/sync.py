"""
sync.py — Google data sync trigger.

POST /api/sync — pull fresh events (Google Calendar) and contacts (Google People API) into memory.
Tasks and goals are managed via the dashboard; they are not synced from external sources.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Sync"])


@router.post("/sync")
def trigger_sync(user_id: str = Depends(get_current_user)):
    """
    Pull fresh events from Google Calendar and contacts from Google People API,
    and persist both to the user's memory store.
    """
    try:
        import memory as mem
        from input.ingestion_service import IngestionService
        svc = IngestionService(mem)
        svc.ingest_all(user_id)
        ctx = mem.build_user_context(user_id)
        data = ctx.model_dump(mode="json") if hasattr(ctx, "model_dump") else ctx
        return {
            "status": "ok",
            "synced": {
                "events":   len(data.get("events", [])),
                "contacts": len(data.get("contacts", [])),
            },
        }
    except Exception as exc:
        logger.error("Sync failed for user=%s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
