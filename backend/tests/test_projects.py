import asyncio
from datetime import datetime, timezone

from bson import ObjectId

from app.services import quota
from worker.handlers.delete_project import delete_project


def test_project_crud(client, make_user):
    headers, _, _ = make_user()
    created = client.post("/api/projects", headers=headers, json={"name": "Smart Attendance"})
    assert created.status_code == 201
    pid = created.json()["id"]

    assert [p["id"] for p in client.get("/api/projects", headers=headers).json()] == [pid]
    assert client.post("/api/projects", headers=headers, json={"name": "Smart Attendance"}).status_code == 409

    renamed = client.patch(f"/api/projects/{pid}", headers=headers, json={"name": "Smart Attendance v2"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Smart Attendance v2"

    assert client.delete(f"/api/projects/{pid}", headers=headers).status_code == 202
    assert client.get("/api/projects", headers=headers).json() == []
    assert client.get(f"/api/projects/{pid}", headers=headers).status_code == 404


def test_students_cannot_access_each_others_projects(client, make_user):
    a_headers, _, _ = make_user()
    b_headers, _, _ = make_user()
    pid = client.post("/api/projects", headers=a_headers, json={"name": "A's project"}).json()["id"]

    assert client.get(f"/api/projects/{pid}", headers=b_headers).status_code == 404
    assert client.patch(f"/api/projects/{pid}", headers=b_headers, json={"name": "hacked"}).status_code == 404
    assert client.delete(f"/api/projects/{pid}", headers=b_headers).status_code == 404
    assert client.get("/api/projects", headers=b_headers).json() == []
    assert client.get(f"/api/projects/{pid}", headers=a_headers).json()["name"] == "A's project"

    assert client.get(f"/api/projects/{pid}").status_code == 401
    assert client.get("/api/projects/not-an-id", headers=a_headers).status_code == 404


def test_delete_project_job_removes_everything(client, db, make_user):
    headers, user, _ = make_user()
    pid = client.post("/api/projects", headers=headers, json={"name": "To delete"}).json()["id"]
    uid, oid = ObjectId(user["id"]), ObjectId(pid)
    db.artifacts.insert_one({"user_id": uid, "project_id": oid, "size_bytes": 1000})  # no storage_key
    db.chunks.insert_one({"user_id": uid, "project_id": oid, "text": "x"})
    db.users.update_one({"_id": uid}, {"$set": {"storage_used_bytes": 1000}})

    client.delete(f"/api/projects/{pid}", headers=headers)
    job = db.jobs.find_one({"type": "delete_project", "project_id": oid})
    delete_project(db, job)

    assert db.projects.count_documents({"_id": oid}) == 0
    assert db.artifacts.count_documents({"project_id": oid}) == 0
    assert db.chunks.count_documents({"project_id": oid}) == 0
    assert db.users.find_one({"_id": uid})["storage_used_bytes"] == 0


def test_quota_reserve_never_exceeds_limit(db):
    from pymongo import AsyncMongoClient

    from app.core.config import get_settings

    uid = db.users.insert_one({"email": f"q-{ObjectId()}@test.com", "storage_used_bytes": 0,
                               "created_at": datetime.now(timezone.utc)}).inserted_id
    limit = 100 * 1024 * 1024

    async def run():
        # Own client: the app's client is bound to the TestClient's event loop.
        client = AsyncMongoClient(get_settings().mongodb_uri)
        adb = client[db.name]
        assert await quota.reserve(adb, uid, 60 * 1024 * 1024)
        assert not await quota.reserve(adb, uid, 50 * 1024 * 1024)  # would exceed 100 MB
        assert await quota.reserve(adb, uid, 40 * 1024 * 1024)      # exactly 100 MB is allowed
        await quota.release(adb, uid, 40 * 1024 * 1024)
        await client.close()

    asyncio.run(run())
    assert db.users.find_one({"_id": uid})["storage_used_bytes"] == 60 * 1024 * 1024 < limit
