from pathlib import Path

import pytest
from bson import ObjectId

from app.services import storage
from worker.handlers.ingest_artifact import ingest_artifact

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.fixture(autouse=True)
def memory_storage(monkeypatch):
    """Replace object storage with a dict so tests don't touch Supabase."""
    blobs: dict[str, bytes] = {}
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: blobs.__setitem__(key, data))
    monkeypatch.setattr(storage, "get_object", lambda key: blobs[key])
    monkeypatch.setattr(storage, "delete_object", lambda key: blobs.pop(key, None))
    monkeypatch.setattr(storage, "presigned_download_url", lambda key, exp=300: f"https://signed/{key}")
    return blobs


@pytest.fixture
def project(client, make_user):
    headers, user, _ = make_user()
    pid = client.post("/api/projects", headers=headers, json={"name": "FYP"}).json()["id"]
    return headers, user, pid


def upload(client, headers, pid, kind, filename, data=None):
    data = data if data is not None else (SAMPLES / filename).read_bytes()
    return client.post(f"/api/projects/{pid}/artifacts", headers=headers,
                       data={"kind": kind}, files={"file": (filename, data)})


def run_ingest_jobs(db, pid):
    for job in db.jobs.find({"project_id": ObjectId(pid), "type": "ingest_artifact", "status": "queued"}):
        ingest_artifact(db, {**job, "attempts": 1})


def test_upload_valid_files_and_process(client, db, project, memory_storage):
    headers, user, pid = project
    for kind, name in [("report", "smart_attendance_report.pdf"),
                       ("presentation", "smart_attendance_slides.pptx"),
                       ("code", "face_matcher.py")]:
        res = upload(client, headers, pid, kind, name)
        assert res.status_code == 201, res.text
        assert res.json()["status"] == "queued"
    assert len(memory_storage) == 3

    run_ingest_jobs(db, pid)
    artifacts = client.get(f"/api/projects/{pid}/artifacts", headers=headers).json()
    assert {a["status"] for a in artifacts} == {"ready"}

    report_chunks = list(db.chunks.find({"project_id": ObjectId(pid), "kind": "report"}))
    assert {c["location"]["page"] for c in report_chunks} == set(range(1, 8))
    assert all(c["user_id"] == ObjectId(user["id"]) and len(c["embedding"]) == 768 for c in report_chunks)
    code_chunk = db.chunks.find_one({"project_id": ObjectId(pid), "kind": "code"})
    assert code_chunk["location"] == {"file": "face_matcher.py", "line_start": 1, "line_end": 25}
    slide_chunk = db.chunks.find_one({"project_id": ObjectId(pid), "kind": "presentation", "location.slide": 4})
    assert slide_chunk["section"] == "Architecture"

    me = client.get("/api/users/me", headers=headers).json()
    assert me["storage_used_bytes"] == sum(a["size_bytes"] for a in artifacts)


@pytest.mark.parametrize("kind,name,data,message", [
    ("report", "scanned_image.pdf", None, "no readable text"),
    ("code", "binary.py", None, "Binary"),
    ("report", "smart_attendance_slides.pptx", None, "PDF"),
    ("code", "photo.png", b"\x89PNG\r\n", "Code files must be one of"),
    ("code", "latin.py", "café".encode("latin-1"), "UTF-8"),
    ("presentation", "archive.zip", b"PK\x03\x04junk", "PPTX or text-readable PDF"),
    ("report", "fake.pdf", b"MZ\x90\x00 executable", "not a valid PDF"),
    ("code", "big.py", b"x = 1\n" * 200_000, "1 MB"),
])
def test_rejects_invalid_files(client, project, kind, name, data, message, memory_storage):
    headers, _, pid = project
    res = upload(client, headers, pid, kind, name, data)
    assert res.status_code == 422
    assert message in res.json()["detail"]
    assert memory_storage == {}


def test_max_five_code_files(client, project):
    headers, _, pid = project
    for i in range(5):
        assert upload(client, headers, pid, "code", f"f{i}.py", b"print(1)\n").status_code == 201
    res = upload(client, headers, pid, "code", "f5.py", b"print(1)\n")
    assert res.status_code == 422 and "at most 5" in res.json()["detail"]


def test_quota_limit(client, db, project):
    headers, user, pid = project
    db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"storage_used_bytes": 100 * 1024 * 1024 - 100}})
    res = upload(client, headers, pid, "report", "smart_attendance_report.pdf")
    assert res.status_code == 413 and "Storage limit" in res.json()["detail"]


def test_replace_and_delete(client, db, project, memory_storage):
    headers, user, pid = project
    aid = upload(client, headers, pid, "code", "face_matcher.py").json()["id"]
    run_ingest_jobs(db, pid)

    new_code = b"def hello():\n    return 'v2'\n"
    res = client.put(f"/api/projects/{pid}/artifacts/{aid}", headers=headers, files={"file": ("face_matcher.py", new_code)})
    assert res.status_code == 200 and res.json()["version"] == 2
    assert db.chunks.count_documents({"artifact_id": ObjectId(aid), "is_active": True}) == 0
    assert len(memory_storage) == 1
    assert client.get("/api/users/me", headers=headers).json()["storage_used_bytes"] == len(new_code)

    run_ingest_jobs(db, pid)
    chunks = list(db.chunks.find({"artifact_id": ObjectId(aid)}))
    assert len(chunks) == 1 and chunks[0]["artifact_version"] == 2 and "v2" in chunks[0]["text"]

    assert client.delete(f"/api/projects/{pid}/artifacts/{aid}", headers=headers).status_code == 204
    assert db.chunks.count_documents({"artifact_id": ObjectId(aid)}) == 0
    assert memory_storage == {}
    assert client.get("/api/users/me", headers=headers).json()["storage_used_bytes"] == 0


def test_other_student_cannot_touch_files(client, make_user, project):
    headers, _, pid = project
    aid = upload(client, headers, pid, "code", "face_matcher.py").json()["id"]
    other, _, _ = make_user()
    assert client.get(f"/api/projects/{pid}/artifacts", headers=other).status_code == 404
    assert upload(client, other, pid, "code", "x.py", b"print(1)").status_code == 404
    assert client.get(f"/api/projects/{pid}/artifacts/{aid}/download", headers=other).status_code == 404
    assert client.delete(f"/api/projects/{pid}/artifacts/{aid}", headers=other).status_code == 404


def test_cancel_then_retry(client, db, project):
    headers, _, pid = project
    aid = upload(client, headers, pid, "code", "face_matcher.py").json()["id"]
    assert client.post(f"/api/projects/{pid}/artifacts/{aid}/cancel", headers=headers).json()["status"] == "canceled"
    run_ingest_jobs(db, pid)  # canceled job is not run
    assert db.artifacts.find_one({"_id": ObjectId(aid)})["status"] == "canceled"

    assert client.post(f"/api/projects/{pid}/artifacts/{aid}/retry", headers=headers).json()["status"] == "queued"
    run_ingest_jobs(db, pid)
    assert db.artifacts.find_one({"_id": ObjectId(aid)})["status"] == "ready"


def test_download_url(client, project):
    headers, _, pid = project
    aid = upload(client, headers, pid, "code", "face_matcher.py").json()["id"]
    res = client.get(f"/api/projects/{pid}/artifacts/{aid}/download", headers=headers)
    assert res.status_code == 200 and res.json()["url"].startswith("https://signed/")
