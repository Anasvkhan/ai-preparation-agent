from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.serializers import project_out
from app.core.deps import get_current_user, get_owned_project
from app.db.mongo import get_async_db
from app.models.schemas import ProjectIn, ProjectOut
from app.services.jobs import new_job

router = APIRouter(prefix="/projects", tags=["projects"])


async def _ensure_unique_name(db, user_id, name: str, exclude_id=None) -> None:
    query = {"user_id": user_id, "name": name, "status": "active"}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    if await db.projects.find_one(query, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a project with this name")


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectIn, user: dict = Depends(get_current_user)):
    db = get_async_db()
    await _ensure_unique_name(db, user["_id"], body.name)
    now = datetime.now(timezone.utc)
    project = {"user_id": user["_id"], "name": body.name, "status": "active", "created_at": now, "updated_at": now}
    project["_id"] = (await db.projects.insert_one(project)).inserted_id
    return project_out(project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: dict = Depends(get_current_user)):
    cursor = get_async_db().projects.find({"user_id": user["_id"], "status": "active"}).sort("updated_at", -1)
    return [project_out(p) async for p in cursor]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project: dict = Depends(get_owned_project)):
    if project.get("status") != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project_out(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def rename_project(body: ProjectIn, project: dict = Depends(get_owned_project)):
    if project.get("status") != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    db = get_async_db()
    await _ensure_unique_name(db, project["user_id"], body.name, exclude_id=project["_id"])
    changes = {"name": body.name, "updated_at": datetime.now(timezone.utc)}
    await db.projects.update_one({"_id": project["_id"]}, {"$set": changes})
    return project_out({**project, **changes})


@router.delete("/{project_id}", status_code=202)
async def delete_project(project: dict = Depends(get_owned_project)):
    """Hides the project immediately; the worker removes files, chunks and sessions in the background."""
    if project.get("status") != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    db = get_async_db()
    now = datetime.now(timezone.utc)
    await db.projects.update_one({"_id": project["_id"]}, {"$set": {"status": "deleting", "updated_at": now}})
    await db.jobs.insert_one(new_job("delete_project", project["user_id"], project["_id"]))
    return {"status": "deleting"}
