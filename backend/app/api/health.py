import asyncio

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.mongo import get_async_db
from app.services import storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    checks: dict[str, str] = {}

    try:
        await get_async_db().command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {e}"

    try:
        await asyncio.to_thread(storage.check_bucket)
        checks["storage"] = "ok"
    except Exception as e:
        checks["storage"] = f"error: {e}"

    s = get_settings()
    checks["llm_provider"] = s.llm_provider
    checks["embedding_provider"] = s.embedding_provider

    ok = checks["mongodb"] == "ok" and checks["storage"] == "ok"
    return {"status": "ok" if ok else "degraded", "checks": checks}
