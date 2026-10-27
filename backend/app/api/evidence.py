"""Read-only views over a project's processed evidence: outline (files + topics) and semantic search."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_owned_project, parse_object_id
from app.db.mongo import get_async_db
from app.services.embeddings import embed_query
from app.services.retrieval import citation_label, scope_filter, search_async

router = APIRouter(prefix="/projects/{project_id}", tags=["evidence"])


def _active(project: dict) -> dict:
    if project.get("status") != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.get("/outline")
async def outline(project: dict = Depends(get_owned_project)):
    """Ready files with their topics (sections / slide titles / code files) for Focused Practice."""
    _active(project)
    db = get_async_db()
    pipeline = [
        {"$match": scope_filter(project["user_id"], project["_id"])},
        {"$group": {"_id": {"artifact_id": "$artifact_id", "topic": "$topic"}, "chunks": {"$sum": 1},
                    "first": {"$min": "$order"}}},
        {"$sort": {"first": 1}},
    ]
    topics_by_artifact: dict = {}
    async for row in await db.chunks.aggregate(pipeline):
        topics_by_artifact.setdefault(row["_id"]["artifact_id"], []).append(
            {"topic": row["_id"]["topic"], "chunks": row["chunks"]})

    files = []
    async for a in db.artifacts.find({"project_id": project["_id"], "user_id": project["user_id"], "status": "ready"}):
        topics = topics_by_artifact.get(a["_id"], [])
        files.append({"id": str(a["_id"]), "filename": a["filename"], "kind": a["kind"],
                      "chunk_count": sum(t["chunks"] for t in topics), "topics": topics})
    return {"ready": bool(files), "files": files}


@router.get("/search")
async def search(
    q: str = Query(min_length=2, max_length=300),
    artifact_id: list[str] = Query(default=[]),
    topic: list[str] = Query(default=[]),
    limit: int = Query(default=5, ge=1, le=20),
    project: dict = Depends(get_owned_project),
):
    _active(project)
    try:
        vector = await asyncio.to_thread(embed_query, q)
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Embedding service unavailable, try again")
    filters = scope_filter(project["user_id"], project["_id"],
                           [parse_object_id(a) for a in artifact_id] or None, topic or None)
    results = await search_async(get_async_db(), vector, filters, limit)
    return [
        {"chunk_id": str(r["_id"]), "artifact_id": str(r["artifact_id"]), "filename": r["filename"],
         "kind": r["kind"], "topic": r["topic"], "location": r["location"], "label": citation_label(r),
         "score": round(r["score"], 4), "text": r["text"][:500]}
        for r in results
    ]
