"""Viva practice sessions. FYP-I: create a session and generate traceable questions."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.core.deps import get_owned_project, parse_object_id
from app.db.mongo import get_async_db
from app.services.evidence import MAX_QUESTIONS, MIN_QUESTIONS, supported_question_count
from app.services.jobs import new_job
from app.services.retrieval import scope_filter

router = APIRouter(prefix="/projects/{project_id}/sessions", tags=["sessions"])


class SessionIn(BaseModel):
    scope: Literal["full", "focused"] = "full"
    artifact_ids: list[str] = Field(default_factory=list, max_length=10)
    topics: list[str] = Field(default_factory=list, max_length=30)
    query: str | None = Field(default=None, max_length=200)
    question_count: int = Field(default=10, ge=MIN_QUESTIONS, le=MAX_QUESTIONS)

    @model_validator(mode="after")
    def focused_needs_focus(self):
        if self.scope == "focused" and not (self.artifact_ids or self.topics or (self.query or "").strip()):
            raise ValueError("Focused practice needs at least one file, topic or search phrase")
        if self.scope == "full":
            self.artifact_ids, self.topics, self.query = [], [], None
        return self


def session_out(s: dict) -> dict:
    return {
        "id": str(s["_id"]),
        "scope": s["scope"],
        "focus": {
            "artifact_ids": [str(a) for a in s["focus"].get("artifact_ids", [])],
            "topics": s["focus"].get("topics", []),
            "query": s["focus"].get("query"),
        },
        "question_count": s["question_count"],
        "status": s["status"],
        "error": s.get("error"),
        "created_at": s["created_at"],
    }


def _active(project: dict) -> dict:
    if project.get("status") != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.post("", status_code=202)
async def create_session(body: SessionIn, project: dict = Depends(get_owned_project)):
    _active(project)
    db = get_async_db()
    artifact_ids = [parse_object_id(a) for a in body.artifact_ids]

    if not await db.artifacts.find_one({"project_id": project["_id"], "user_id": project["user_id"],
                                        "status": "ready"}):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "At least one uploaded file must be Ready before you can start a viva")

    filters = scope_filter(project["user_id"], project["_id"], artifact_ids or None, body.topics or None)
    chunks = [c async for c in db.chunks.find(filters, {"text": 1, "artifact_id": 1, "topic": 1, "location": 1})]
    # A free-text focus is resolved by vector search in the worker; it can only narrow the scope further,
    # so the check here is an upper bound and the worker re-checks against what it actually retrieves.
    supported = supported_question_count(chunks)
    if supported < MIN_QUESTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {
            "message": (f"The selected evidence can only support about {supported} distinct questions. "
                        f"Upload more evidence or select more files/topics (minimum {MIN_QUESTIONS})."),
            "max_supported": supported,
        })
    if body.question_count > supported:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {
            "message": (f"The selected evidence can support at most {supported} questions. "
                        f"Lower the question count to {supported} or add more evidence."),
            "max_supported": supported,
        })

    now = datetime.now(timezone.utc)
    session = {
        "user_id": project["user_id"],
        "project_id": project["_id"],
        "scope": body.scope,
        "focus": {"artifact_ids": artifact_ids, "topics": body.topics, "query": (body.query or "").strip() or None},
        "question_count": body.question_count,
        "status": "generating",
        "created_at": now,
        "updated_at": now,
    }
    session["_id"] = (await db.sessions.insert_one(session)).inserted_id
    await db.jobs.insert_one(new_job("generate_questions", project["user_id"], project["_id"],
                                     session_id=session["_id"]))
    return session_out(session)


@router.get("")
async def list_sessions(project: dict = Depends(get_owned_project)):
    _active(project)
    cursor = get_async_db().sessions.find({"project_id": project["_id"], "user_id": project["user_id"]})
    return [session_out(s) async for s in cursor.sort("created_at", -1).limit(50)]


@router.get("/{session_id}")
async def get_session(session_id: str, project: dict = Depends(get_owned_project)):
    db = get_async_db()
    session = await db.sessions.find_one({"_id": parse_object_id(session_id), "project_id": project["_id"],
                                          "user_id": project["user_id"]})
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    questions = [q async for q in db.questions.find({"session_id": session["_id"]}).sort("order", 1)]
    cited_ids = {c["artifact_id"] for q in questions for c in q["citations"]}
    live = {a["_id"]: a["version"] async for a in db.artifacts.find({"_id": {"$in": list(cited_ids)}},
                                                                     {"version": 1})}

    def citation_out(c: dict) -> dict:
        current = live.get(c["artifact_id"])
        note = None if current == c["artifact_version"] else (
            "Source no longer available" if current is None else "Source was replaced by a newer version")
        return {"label": c["label"], "filename": c["filename"], "kind": c["kind"], "location": c["location"],
                "quote": c["quote"], "artifact_id": str(c["artifact_id"]), "available": note is None, "note": note}

    return {
        **session_out(session),
        "questions": [
            {"id": str(q["_id"]), "order": q["order"], "text": q["text"], "topic": q["topic"],
             "difficulty": q["difficulty"], "expected_points": q["expected_points"],
             "citations": [citation_out(c) for c in q["citations"]]}
            for q in questions
        ],
    }
