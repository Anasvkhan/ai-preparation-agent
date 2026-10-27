"""Extract -> chunk -> embed -> store, for one artifact version."""
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services import storage
from app.services.embeddings import embed_texts
from worker.chunking import chunk_segments
from worker.extractors import extract


class JobCanceled(Exception):
    pass


def _now():
    return datetime.now(timezone.utc)


def _topic(section: str) -> str:
    return " ".join(section.split())[:80] or "General"


def ingest_artifact(db, job) -> None:
    artifact = db.artifacts.find_one({"_id": job["artifact_id"], "user_id": job["user_id"]})
    if not artifact or artifact["version"] != job["version"]:
        return  # deleted or replaced since the job was queued: nothing to do

    def check_canceled():
        if db.jobs.find_one({"_id": job["_id"]}, {"status": 1})["status"] == "canceled":
            raise JobCanceled()

    def set_status(**fields):
        db.artifacts.update_one({"_id": artifact["_id"], "version": job["version"]},
                                {"$set": {**fields, "updated_at": _now()}})

    set_status(status="processing", error=None)
    try:
        data = storage.get_object(artifact["storage_key"])
        segments, meta = extract(artifact["file_format"], data, artifact["filename"])
        chunks = chunk_segments(segments)
        if not chunks:
            raise ValueError("No readable text was found in this file")
        check_canceled()

        vectors = embed_texts([c["text"] for c in chunks])
        check_canceled()

        base = {
            "user_id": artifact["user_id"],
            "project_id": artifact["project_id"],
            "artifact_id": artifact["_id"],
            "artifact_version": artifact["version"],
            "kind": artifact["kind"],
            "filename": artifact["filename"],
            "is_active": True,
            "embedding_model": get_settings().embedding_model,
            "created_at": _now(),
        }
        docs = [{**base, "order": i, "text": c["text"], "location": c["location"], "section": c["section"],
                 "topic": _topic(c["section"]), "embedding": vec}
                for i, (c, vec) in enumerate(zip(chunks, vectors))]

        # Idempotent: a retry replaces whatever a previous attempt wrote for this version.
        db.chunks.delete_many({"artifact_id": artifact["_id"], "artifact_version": artifact["version"]})
        db.chunks.insert_many(docs)
        db.chunks.delete_many({"artifact_id": artifact["_id"], "artifact_version": {"$ne": artifact["version"]}})

        set_status(status="ready", chunk_count=len(docs), page_count=meta.get("page_count"),
                   topics=sorted({d["topic"] for d in docs}))
    except JobCanceled:
        db.chunks.delete_many({"artifact_id": artifact["_id"], "artifact_version": artifact["version"]})
        set_status(status="canceled")
    except Exception as e:
        set_status(status="failed", error=str(e)[:300])  # student sees it and can press Retry
        raise
