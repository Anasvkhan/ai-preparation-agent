"""Per-student storage quota (100 MB across all retained original uploads).

reserve() is a single conditional update, so two parallel uploads can never push a user over quota.
"""
from bson import ObjectId

from app.core.config import get_settings


async def reserve(db, user_id: ObjectId, size_bytes: int) -> bool:
    limit = get_settings().quota_bytes
    result = await db.users.update_one(
        {"_id": user_id, "storage_used_bytes": {"$lte": limit - size_bytes}},
        {"$inc": {"storage_used_bytes": size_bytes}},
    )
    return result.modified_count == 1


async def release(db, user_id: ObjectId, size_bytes: int) -> None:
    await db.users.update_one({"_id": user_id}, {"$inc": {"storage_used_bytes": -size_bytes}})


def recompute_sync(db, user_id: ObjectId) -> int:
    """Recalculate usage from the artifacts actually stored (used by the worker after deletes)."""
    total = sum(a["size_bytes"] for a in db.artifacts.find({"user_id": user_id}, {"size_bytes": 1}))
    db.users.update_one({"_id": user_id}, {"$set": {"storage_used_bytes": total}})
    return total
