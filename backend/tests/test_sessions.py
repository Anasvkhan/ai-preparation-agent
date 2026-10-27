from bson import ObjectId

from tests.test_artifacts import memory_storage, run_ingest_jobs, upload  # noqa: F401  (fixture reuse)
from worker.handlers.generate_questions import _is_duplicate, _normalize, generate_questions


def _project_with_files(client, db, make_user, files=(("report", "smart_attendance_report.pdf"),
                                                      ("presentation", "smart_attendance_slides.pptx"),
                                                      ("code", "face_matcher.py"))):
    headers, user, _ = make_user()
    pid = client.post("/api/projects", headers=headers, json={"name": "FYP"}).json()["id"]
    ids = {name: upload(client, headers, pid, kind, name).json()["id"] for kind, name in files}
    run_ingest_jobs(db, pid)
    return headers, pid, ids


def _run_generation(db, session_id):
    job = db.jobs.find_one({"session_id": ObjectId(session_id), "type": "generate_questions"})
    generate_questions(db, {**job, "attempts": 1})


def test_needs_a_ready_file(client, make_user):
    headers, _, _ = make_user()
    pid = client.post("/api/projects", headers=headers, json={"name": "Empty"}).json()["id"]
    res = client.post(f"/api/projects/{pid}/sessions", headers=headers, json={})
    assert res.status_code == 409 and "Ready" in res.json()["detail"]


def test_full_viva_generates_traceable_questions(client, db, make_user):
    headers, pid, ids = _project_with_files(client, db, make_user)
    res = client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"scope": "full", "question_count": 12})
    assert res.status_code == 202 and res.json()["status"] == "generating"
    sid = res.json()["id"]

    _run_generation(db, sid)
    session = client.get(f"/api/projects/{pid}/sessions/{sid}", headers=headers).json()
    assert session["status"] == "ready"
    assert len(session["questions"]) == 12
    assert len({q["text"] for q in session["questions"]}) == 12
    for q in session["questions"]:
        assert q["citations"], "every question must cite evidence"
        for c in q["citations"]:
            assert c["available"] and c["artifact_id"] in ids.values()
            assert any(k in c["location"] for k in ("page", "slide", "file"))
    assert db.usage_logs.count_documents({"session_id": ObjectId(sid)}) >= 1

    listed = client.get(f"/api/projects/{pid}/sessions", headers=headers).json()
    assert listed[0]["id"] == sid


def test_question_count_limits(client, db, make_user):
    headers, pid, _ = _project_with_files(client, db, make_user)
    assert client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"question_count": 9}).status_code == 422
    assert client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"question_count": 21}).status_code == 422


def test_insufficient_evidence_asks_for_more(client, db, make_user):
    headers, pid, _ = _project_with_files(client, db, make_user, files=(("code", "face_matcher.py"),))
    res = client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"question_count": 10})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "Upload more evidence" in detail["message"] and detail["max_supported"] < 10


def test_lower_count_suggested_when_partly_supported(client, db, make_user):
    headers, pid, _ = _project_with_files(client, db, make_user, files=(("report", "smart_attendance_report.pdf"),))
    res = client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"question_count": 20})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "Lower the question count" in detail["message"] and 10 <= detail["max_supported"] < 20


def test_focused_on_file_only_cites_that_file(client, db, make_user):
    headers, pid, ids = _project_with_files(client, db, make_user)
    report_id = ids["smart_attendance_report.pdf"]
    res = client.post(f"/api/projects/{pid}/sessions", headers=headers,
                      json={"scope": "focused", "artifact_ids": [report_id], "question_count": 10})
    assert res.status_code == 202, res.text
    _run_generation(db, res.json()["id"])
    session = client.get(f"/api/projects/{pid}/sessions/{res.json()['id']}", headers=headers).json()
    assert session["status"] == "ready"
    assert {c["artifact_id"] for q in session["questions"] for c in q["citations"]} == {report_id}


def test_focused_needs_a_focus(client, db, make_user):
    headers, pid, _ = _project_with_files(client, db, make_user)
    assert client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"scope": "focused"}).status_code == 422


def test_deleted_source_shows_unavailable(client, db, make_user):
    headers, pid, ids = _project_with_files(client, db, make_user)
    sid = client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"question_count": 10}).json()["id"]
    _run_generation(db, sid)
    client.delete(f"/api/projects/{pid}/artifacts/{ids['smart_attendance_report.pdf']}", headers=headers)

    session = client.get(f"/api/projects/{pid}/sessions/{sid}", headers=headers).json()
    report_cites = [c for q in session["questions"] for c in q["citations"]
                    if c["filename"] == "smart_attendance_report.pdf"]
    assert report_cites and all(not c["available"] and c["note"] == "Source no longer available"
                                for c in report_cites)
    assert all(c["quote"] for c in report_cites)  # snapshot kept


def test_other_student_cannot_see_sessions(client, db, make_user):
    headers, pid, _ = _project_with_files(client, db, make_user, files=(("report", "smart_attendance_report.pdf"),))
    sid = client.post(f"/api/projects/{pid}/sessions", headers=headers, json={"question_count": 10}).json()["id"]
    other, _, _ = make_user()
    assert client.get(f"/api/projects/{pid}/sessions/{sid}", headers=other).status_code == 404
    assert client.post(f"/api/projects/{pid}/sessions", headers=other, json={}).status_code == 404


def test_duplicate_detection():
    seen = [_normalize("Why did you choose FaceNet instead of Haar cascades?")]
    assert _is_duplicate("Why did you choose FaceNet over Haar cascades?", seen)
    assert not _is_duplicate("How are face embeddings encrypted in the database?", seen)


def test_focus_query_keeps_only_close_matches(monkeypatch):
    import importlib

    gq = importlib.import_module("worker.handlers.generate_questions")  # module, not the same-named function

    scores = [0.878, 0.868, 0.858, 0.851, 0.842, 0.80, 0.79]
    fake = [{"score": s, "text": f"chunk {i}", "topic": "T", "filename": "r.pdf", "location": {"page": i + 1}}
            for i, s in enumerate(scores)]
    monkeypatch.setattr(gq, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(gq, "search_sync", lambda db, v, f, limit: fake)
    session = {"user_id": ObjectId(), "project_id": ObjectId(), "question_count": 10, "scope": "focused",
               "focus": {"query": "spoofing", "topics": [], "artifact_ids": []}}
    picked = gq.select_evidence(None, session)
    assert [p["score"] for p in picked] == [0.878, 0.868, 0.858, 0.851, 0.842]  # within 0.04 of best

    prompt = gq.build_prompt(picked, 10, [], gq.describe_focus(session))
    assert 'focused practice on the topic "spoofing"' in prompt
    assert gq.describe_focus({**session, "scope": "full"}) is None
