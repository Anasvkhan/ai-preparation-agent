"""Background worker. Run: python -m worker.main

Claims jobs atomically from the `jobs` collection, keeps a heartbeat while running,
and re-queues jobs whose worker died (stale heartbeat).
"""
import logging
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from app.db.mongo import get_sync_db

from worker.handlers import HANDLERS
from worker.retry import is_transient

POLL_SECONDS = 2
HEARTBEAT_SECONDS = 15
STALE_AFTER = timedelta(minutes=2)
RETRY_DELAY_SECONDS = 15
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"

log = logging.getLogger("worker")


def now() -> datetime:
    return datetime.now(timezone.utc)


def claim_job(db):
    return db.jobs.find_one_and_update(
        {"status": "queued", "$or": [{"run_after": {"$exists": False}}, {"run_after": {"$lte": now()}}]},
        {
            "$set": {"status": "processing", "locked_by": WORKER_ID, "heartbeat_at": now(), "started_at": now()},
            "$inc": {"attempts": 1},
        },
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


def mirror_status(db, job, status: str, error: str | None) -> None:
    """Keep the student-visible record (file / practice session) in step with its job."""
    if job.get("artifact_id"):
        db.artifacts.update_one({"_id": job["artifact_id"], "version": job.get("version")},
                                {"$set": {"status": status, "error": error, "updated_at": now()}})
    if job.get("session_id"):
        session_status = {"queued": "generating", "failed": "failed"}.get(status, status)
        db.sessions.update_one({"_id": job["session_id"]}, {"$set": {"status": session_status, "error": error}})


def requeue_stale_jobs(db) -> None:
    cutoff = now() - STALE_AFTER
    stale = {"status": "processing", "heartbeat_at": {"$lt": cutoff}}
    for job in db.jobs.find(stale):
        exhausted = job.get("attempts", 0) >= job.get("max_attempts", 3)
        new_status = "failed" if exhausted else "queued"
        result = db.jobs.update_one(
            {"_id": job["_id"], "status": "processing"},
            {"$set": {"status": new_status, "error": "worker stopped responding"}},
        )
        if result.modified_count:
            mirror_status(db, job, new_status, "Processing was interrupted" if exhausted else None)


def _heartbeat(db, job_id, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_SECONDS):
        db.jobs.update_one({"_id": job_id, "locked_by": WORKER_ID}, {"$set": {"heartbeat_at": now()}})


def run_job(db, job) -> None:
    handler = HANDLERS.get(job["type"])
    stop = threading.Event()
    threading.Thread(target=_heartbeat, args=(db, job["_id"], stop), daemon=True).start()
    try:
        if handler is None:
            raise ValueError(f"no handler for job type {job['type']!r}")
        handler(db, job)
        # Don't overwrite a cancel that happened while the job was running.
        db.jobs.update_one(
            {"_id": job["_id"], "status": "processing"},
            {"$set": {"status": "ready", "finished_at": now(), "error": None}},
        )
    except Exception as e:
        if is_transient(e) and job.get("attempts", 1) < job.get("max_attempts", 3):
            delay = RETRY_DELAY_SECONDS * job.get("attempts", 1)
            log.warning("job %s hit a temporary error, retrying in %ss: %s", job["_id"], delay, e)
            result = db.jobs.update_one(
                {"_id": job["_id"], "status": "processing"},
                {"$set": {"status": "queued", "run_after": now() + timedelta(seconds=delay), "error": str(e)[:500]}},
            )
            if result.modified_count:
                mirror_status(db, job, "queued", None)
            return
        log.exception("job %s failed", job["_id"])
        db.jobs.update_one(
            {"_id": job["_id"], "status": "processing"},
            {"$set": {"status": "failed", "finished_at": now(), "error": str(e)[:500]}},
        )
    finally:
        stop.set()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    db = get_sync_db()
    log.info("worker %s started", WORKER_ID)
    last_sweep = 0.0
    while True:
        if time.time() - last_sweep > 30:
            requeue_stale_jobs(db)
            last_sweep = time.time()
        job = claim_job(db)
        if job:
            log.info("running job %s (%s)", job["_id"], job["type"])
            run_job(db, job)
        else:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
