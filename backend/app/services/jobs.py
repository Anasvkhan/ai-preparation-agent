from datetime import datetime, timezone


def new_job(job_type: str, user_id, project_id, **payload) -> dict:
    return {
        "type": job_type,
        "user_id": user_id,
        "project_id": project_id,
        "status": "queued",
        "attempts": 0,
        "max_attempts": 3,
        "created_at": datetime.now(timezone.utc),
        **payload,
    }
