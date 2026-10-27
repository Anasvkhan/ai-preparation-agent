import ssl
from datetime import datetime, timedelta, timezone

import pytest

from worker import main as worker
from worker.retry import is_transient


@pytest.fixture(autouse=True)
def empty_queue(db):
    db.jobs.delete_many({})  # leftovers from other test files would be claimed first


def _job(db, job_type, **extra):
    doc = {"type": job_type, "status": "queued", "attempts": 0, "max_attempts": 3,
           "created_at": datetime.now(timezone.utc), **extra}
    doc["_id"] = db.jobs.insert_one(doc).inserted_id
    return doc


def test_transient_detection():
    assert is_transient(ssl.SSLError("EOF occurred"))
    assert is_transient(TimeoutError())
    try:
        try:
            raise ConnectionResetError()
        except ConnectionResetError as inner:
            raise RuntimeError("wrapped") from inner
    except RuntimeError as e:
        assert is_transient(e)
    assert not is_transient(ValueError("No readable text"))


def test_transient_error_requeues_with_delay(db, monkeypatch):
    artifact_id = db.artifacts.insert_one({"status": "processing", "version": 1}).inserted_id
    _job(db, "flaky", artifact_id=artifact_id, version=1)

    def flaky(db_, job):
        raise ssl.SSLError("EOF occurred in violation of protocol")

    monkeypatch.setitem(worker.HANDLERS, "flaky", flaky)
    job = worker.claim_job(db)
    worker.run_job(db, job)

    saved = db.jobs.find_one({"_id": job["_id"]})
    assert saved["status"] == "queued"
    assert saved["run_after"].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
    assert db.artifacts.find_one({"_id": artifact_id})["status"] == "queued"
    assert worker.claim_job(db) is None  # not picked up again until run_after


def test_permanent_error_fails_immediately(db, monkeypatch):
    _job(db, "broken")
    monkeypatch.setitem(worker.HANDLERS, "broken", lambda d, j: (_ for _ in ()).throw(ValueError("bad file")))
    job = worker.claim_job(db)
    worker.run_job(db, job)
    assert db.jobs.find_one({"_id": job["_id"]})["status"] == "failed"


def test_stale_job_is_requeued(db):
    job = _job(db, "ping", status="processing", attempts=1,
               heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    worker.requeue_stale_jobs(db)
    assert db.jobs.find_one({"_id": job["_id"]})["status"] == "queued"
