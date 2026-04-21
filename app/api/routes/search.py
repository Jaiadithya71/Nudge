from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

import api.dependencies  # noqa: F401 — ensures sys.path patched
import memory as mem
import vector_db as vdb

from api.dependencies import get_current_user

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=50)


@router.post("/search/tasks")
def search_tasks(
    body: SearchRequest,
    user_id: str = Depends(get_current_user),
):
    """Semantic search over the user's tasks ChromaDB collection.

    Returns: [{"task_id": str, "title": str, "score": float, "snippet": str}, ...]
    """
    raw = vdb.query_documents(
        user_id=user_id,
        query=body.query,
        entity_type="tasks",
        n_results=body.limit,
    )

    results = []
    for r in raw:
        task_id = r["id"]
        task = mem.get_task(user_id, task_id)
        title = task["title"] if task else task_id
        results.append({
            "task_id": task_id,
            "title": title,
            "score": round(max(0.0, 1.0 - r.get("distance", 0.0)), 4),
            "snippet": r.get("document", ""),
        })

    return results
