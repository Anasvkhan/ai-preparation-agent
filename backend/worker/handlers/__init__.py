"""Job type -> handler(db, job)."""
from worker.handlers.delete_project import delete_project
from worker.handlers.generate_questions import generate_questions
from worker.handlers.ingest_artifact import ingest_artifact


def ping(db, job) -> None:
    """Test job to check the worker loop end to end."""
    db.jobs.update_one({"_id": job["_id"]}, {"$set": {"result": "pong"}})


HANDLERS = {
    "ping": ping,
    "delete_project": delete_project,
    "ingest_artifact": ingest_artifact,
    "generate_questions": generate_questions,
}
