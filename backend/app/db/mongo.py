from pymongo import AsyncMongoClient, MongoClient

from app.core.config import get_settings

_async_client: AsyncMongoClient | None = None


def get_async_db():
    """Database handle for the FastAPI app (async)."""
    global _async_client
    settings = get_settings()
    if _async_client is None:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is not set in backend/.env")
        _async_client = AsyncMongoClient(settings.mongodb_uri)
    return _async_client[settings.mongodb_db]


def get_sync_db():
    """Database handle for the worker and scripts (sync)."""
    settings = get_settings()
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set in backend/.env")
    return MongoClient(settings.mongodb_uri)[settings.mongodb_db]


async def close_async_client() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.close()
        _async_client = None
