"""
vector_db.py — Per-user ChromaDB isolation for semantic memory.

Each user gets a dedicated persistent Chroma client at:
    data/{user_id}/chroma/

Collections are namespaced per entity type so we can limit search scope.
"""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings

# Module-level client cache so the same client is reused per user_id.
# Tests can call reset_client(user_id) to release the file handle.
_client_cache: dict[str, chromadb.PersistentClient] = {}


def _chroma_path(user_id: str) -> Path:
    """Return (and create) the per-user chroma directory."""
    base = Path(__file__).parent / "data" / user_id / "chroma"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_client(user_id: str) -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client scoped to *user_id* (cached)."""
    if user_id not in _client_cache:
        path = str(_chroma_path(user_id))
        _client_cache[user_id] = chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client_cache[user_id]


def reset_client(user_id: str) -> None:
    """
    Explicitly remove the cached client for *user_id*.

    Call this in tests before shutil.rmtree to release file handles.
    """
    client = _client_cache.pop(user_id, None)
    if client is not None:
        try:
            client._system.stop()  # type: ignore[attr-defined]
        except Exception:
            pass


def get_collection(user_id: str, entity_type: str) -> chromadb.Collection:
    """
    Return (or create) the Chroma collection for a given entity type.

    The collection name is ``{user_id}_{entity_type}`` — this is the primary
    isolation barrier between users inside ChromaDB.
    """
    client = get_client(user_id)
    collection_name = f"{user_id}_{entity_type}"
    # get_or_create is idempotent
    return client.get_or_create_collection(name=collection_name)


def add_document(
    user_id: str,
    entity_type: str,
    doc_id: str,
    text: str,
    metadata: dict | None = None,
) -> None:
    """Upsert a document into the user's entity collection."""
    collection = get_collection(user_id, entity_type)
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata or {}],
    )


def query_documents(
    user_id: str,
    query: str,
    entity_type: str | None = None,
    n_results: int = 10,
) -> list[dict]:
    """
    Semantic search across one or all entity-type collections for *user_id*.

    Returns a flat list of result dicts: {id, document, metadata, distance}.
    """
    # Build list of collections to search
    client = get_client(user_id)
    existing = [c.name for c in client.list_collections()]

    if entity_type:
        target = f"{user_id}_{entity_type}"
        collections_to_search = [target] if target in existing else []
    else:
        collections_to_search = [
            name for name in existing if name.startswith(f"{user_id}_")
        ]

    results: list[dict] = []
    for col_name in collections_to_search:
        collection = client.get_collection(col_name)
        count = collection.count()
        if count == 0:
            continue
        res = collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        for i, doc_id in enumerate(res["ids"][0]):
            results.append(
                {
                    "id": doc_id,
                    "document": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "distance": res["distances"][0][i],
                }
            )

    # Sort by ascending distance (most similar first)
    results.sort(key=lambda r: r["distance"])
    return results[:n_results]
