"""Evidence files (report / presentation / code) inside a project."""
import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.deps import get_owned_project, parse_object_id
from app.db.mongo import get_async_db
from app.services import quota, storage
from app.services.jobs import new_job
from app.services.validation import MAX_CODE_FILES, MAX_DOC_BYTES, ValidationError, validate_upload

router = APIRouter(prefix="/projects/{project_id}/artifacts", tags=["artifacts"])


def artifact_out(a: dict) -> dict:
    return {
        "id": str(a["_id"]),
        "kind": a["kind"],
        "filename": a["filename"],
        "file_format": a["file_format"],
        "size_bytes": a["size_bytes"],
        "version": a["version"],
        "status": a["status"],
        "error": a.get("error"),
        "chunk_count": a.get("chunk_count", 0),
        "page_count": a.get("page_count"),
        "created_at": a["created_at"],
        "updated_at": a["updated_at"],
    }


def _active(project: dict) -> dict:
    if project.get("status") != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_DOC_BYTES + 1)
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is larger than 25 MB")
    return data


async def _validate(kind: str, file: UploadFile, data: bytes):
    try:
        return await asyncio.to_thread(validate_upload, kind, file.filename or "", data)
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


async def _get_artifact(db, project: dict, artifact_id: str) -> dict:
    artifact = await db.artifacts.find_one(
        {"_id": parse_object_id(artifact_id), "project_id": project["_id"], "user_id": project["user_id"]}
    )
    if not artifact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return artifact


async def _store(db, project: dict, artifact_id: ObjectId, version: int, checked, data: bytes) -> str:
    """Reserve quota and upload the bytes. Returns the storage key; releases quota on failure."""
    if not await quota.reserve(db, project["user_id"], len(data)):
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            "Storage limit reached (100 MB). Delete or replace files to free space.")
    key = storage.artifact_key(str(project["user_id"]), str(project["_id"]), str(artifact_id), version,
                               checked.filename)
    try:
        await asyncio.to_thread(storage.put_object, key, data, checked.content_type)
    except Exception:
        await quota.release(db, project["user_id"], len(data))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not save the file to storage, please retry")
    return key


@router.get("")
async def list_artifacts(project: dict = Depends(get_owned_project)):
    _active(project)
    cursor = get_async_db().artifacts.find({"project_id": project["_id"], "user_id": project["user_id"]})
    return [artifact_out(a) async for a in cursor.sort("created_at", 1)]


@router.post("", status_code=201)
async def upload_artifact(
    kind: str = Form(...),
    file: UploadFile = File(...),
    project: dict = Depends(get_owned_project),
):
    _active(project)
    db = get_async_db()
    data = await _read_upload(file)
    checked = await _validate(kind, file, data)

    if kind == "code":
        count = await db.artifacts.count_documents({"project_id": project["_id"], "kind": "code"})
        if count >= MAX_CODE_FILES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"A project can have at most {MAX_CODE_FILES} code files")

    artifact_id = ObjectId()
    key = await _store(db, project, artifact_id, 1, checked, data)
    now = datetime.now(timezone.utc)
    artifact = {
        "_id": artifact_id,
        "user_id": project["user_id"],
        "project_id": project["_id"],
        "kind": kind,
        "filename": checked.filename,
        "file_format": checked.file_format,
        "content_type": checked.content_type,
        "size_bytes": len(data),
        "storage_key": key,
        "version": 1,
        "status": "queued",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.artifacts.insert_one(artifact)
    await db.jobs.insert_one(new_job("ingest_artifact", project["user_id"], project["_id"],
                                     artifact_id=artifact_id, version=1))
    return artifact_out(artifact)


@router.put("/{artifact_id}")
async def replace_artifact(
    artifact_id: str,
    file: UploadFile = File(...),
    project: dict = Depends(get_owned_project),
):
    """Upload a new version. Old chunks stop being used immediately; old questions keep their citations."""
    _active(project)
    db = get_async_db()
    artifact = await _get_artifact(db, project, artifact_id)
    data = await _read_upload(file)
    checked = await _validate(artifact["kind"], file, data)

    version = artifact["version"] + 1
    key = await _store(db, project, artifact["_id"], version, checked, data)
    now = datetime.now(timezone.utc)
    changes = {
        "filename": checked.filename,
        "file_format": checked.file_format,
        "content_type": checked.content_type,
        "size_bytes": len(data),
        "storage_key": key,
        "version": version,
        "status": "queued",
        "error": None,
        "chunk_count": 0,
        "updated_at": now,
    }
    await db.artifacts.update_one({"_id": artifact["_id"]}, {"$set": changes})
    await db.chunks.update_many({"artifact_id": artifact["_id"]}, {"$set": {"is_active": False}})
    await db.jobs.update_many({"artifact_id": artifact["_id"], "status": "queued"}, {"$set": {"status": "canceled"}})
    await db.jobs.insert_one(new_job("ingest_artifact", project["user_id"], project["_id"],
                                     artifact_id=artifact["_id"], version=version))

    # Old version is no longer kept, so its bytes no longer count towards the quota.
    await asyncio.to_thread(storage.delete_object, artifact["storage_key"])
    await quota.release(db, project["user_id"], artifact["size_bytes"])
    return artifact_out({**artifact, **changes})


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(artifact_id: str, project: dict = Depends(get_owned_project)):
    _active(project)
    db = get_async_db()
    artifact = await _get_artifact(db, project, artifact_id)
    await db.jobs.update_many({"artifact_id": artifact["_id"], "status": {"$in": ["queued", "processing"]}},
                              {"$set": {"status": "canceled"}})
    await asyncio.to_thread(storage.delete_object, artifact["storage_key"])
    await db.chunks.delete_many({"artifact_id": artifact["_id"]})
    await db.artifacts.delete_one({"_id": artifact["_id"]})
    await quota.release(db, project["user_id"], artifact["size_bytes"])


@router.get("/{artifact_id}/download")
async def download_url(artifact_id: str, project: dict = Depends(get_owned_project)):
    _active(project)
    artifact = await _get_artifact(get_async_db(), project, artifact_id)
    url = await asyncio.to_thread(storage.presigned_download_url, artifact["storage_key"], 300)
    return {"url": url, "expires_in": 300}


@router.post("/{artifact_id}/retry")
async def retry_processing(artifact_id: str, project: dict = Depends(get_owned_project)):
    _active(project)
    db = get_async_db()
    artifact = await _get_artifact(db, project, artifact_id)
    if artifact["status"] not in {"failed", "canceled"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed or canceled files can be retried")
    await db.artifacts.update_one({"_id": artifact["_id"]}, {"$set": {"status": "queued", "error": None}})
    await db.jobs.insert_one(new_job("ingest_artifact", project["user_id"], project["_id"],
                                     artifact_id=artifact["_id"], version=artifact["version"]))
    return artifact_out({**artifact, "status": "queued", "error": None})


@router.post("/{artifact_id}/cancel")
async def cancel_processing(artifact_id: str, project: dict = Depends(get_owned_project)):
    _active(project)
    db = get_async_db()
    artifact = await _get_artifact(db, project, artifact_id)
    if artifact["status"] not in {"queued", "processing"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only queued or processing files can be canceled")
    await db.jobs.update_many({"artifact_id": artifact["_id"], "status": {"$in": ["queued", "processing"]}},
                              {"$set": {"status": "canceled"}})
    await db.artifacts.update_one({"_id": artifact["_id"]}, {"$set": {"status": "canceled"}})
    return artifact_out({**artifact, "status": "canceled"})
