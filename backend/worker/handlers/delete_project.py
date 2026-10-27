from app.services import quota, storage


def delete_project(db, job) -> None:
    """Remove everything that belongs to a project, then recompute the owner's storage usage.

    Safe to re-run: every step deletes whatever is left.
    """
    user_id, project_id = job["user_id"], job["project_id"]
    scope = {"user_id": user_id, "project_id": project_id}

    # Cancel any other queued/processing work for this project (e.g. ingestion).
    db.jobs.update_many(
        {**scope, "_id": {"$ne": job["_id"]}, "status": {"$in": ["queued", "processing"]}},
        {"$set": {"status": "canceled"}},
    )

    for artifact in db.artifacts.find(scope, {"storage_key": 1}):
        if artifact.get("storage_key"):
            storage.delete_object(artifact["storage_key"])

    session_ids = [s["_id"] for s in db.sessions.find(scope, {"_id": 1})]
    db.answers.delete_many({"session_id": {"$in": session_ids}})
    db.questions.delete_many({"session_id": {"$in": session_ids}})
    db.sessions.delete_many(scope)
    db.chunks.delete_many(scope)
    db.topic_stats.delete_many(scope)
    db.artifacts.delete_many(scope)
    db.projects.delete_one({"_id": project_id, "user_id": user_id})

    quota.recompute_sync(db, user_id)
