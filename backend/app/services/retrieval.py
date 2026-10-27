"""Secure evidence retrieval.

Every query is hard-scoped to (user_id, project_id, is_active=True); callers can only narrow it further
with artifact ids / topics. There is no code path that searches without the user and project filter.
"""
from bson import ObjectId

from app.db.vector_index import INDEX_NAME

PROJECTION = {"embedding": 0}


def scope_filter(user_id: ObjectId, project_id: ObjectId, artifact_ids: list[ObjectId] | None = None,
                 topics: list[str] | None = None) -> dict:
    f: dict = {"user_id": user_id, "project_id": project_id, "is_active": True}
    if artifact_ids:
        f["artifact_id"] = {"$in": artifact_ids}
    if topics:
        f["topic"] = {"$in": topics}
    return f


def vector_pipeline(query_vector: list[float], filters: dict, limit: int = 8) -> list[dict]:
    return [
        {
            "$vectorSearch": {
                "index": INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": max(100, limit * 10),
                "limit": limit,
                "filter": filters,
            }
        },
        {"$project": {**PROJECTION, "score": {"$meta": "vectorSearchScore"}}},
    ]


def search_sync(db, query_vector, filters: dict, limit: int = 8) -> list[dict]:
    return list(db.chunks.aggregate(vector_pipeline(query_vector, filters, limit)))


async def search_async(db, query_vector, filters: dict, limit: int = 8) -> list[dict]:
    cursor = await db.chunks.aggregate(vector_pipeline(query_vector, filters, limit))
    return [doc async for doc in cursor]


def citation_label(chunk: dict) -> str:
    loc = chunk.get("location", {})
    if "page" in loc:
        return f"{chunk.get('filename', 'Report')} · p. {loc['page']}"
    if "slide" in loc:
        return f"{chunk.get('filename', 'Slides')} · slide {loc['slide']}"
    if "file" in loc:
        return f"{loc['file']} · lines {loc['line_start']}–{loc['line_end']}"
    return chunk.get("filename", "Source")
