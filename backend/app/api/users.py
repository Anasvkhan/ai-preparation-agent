from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.api.auth import token_response
from app.api.serializers import user_out
from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.db.mongo import get_async_db
from app.models.schemas import PasswordChangeIn, ProfileUpdateIn, TokenOut, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
async def update_profile(body: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    changes = {}
    if body.name is not None:
        changes["name"] = body.name.strip()
    if body.email is not None:
        changes["email"] = body.email.lower()
    if not changes:
        return user_out(user)
    changes["updated_at"] = datetime.now(timezone.utc)
    try:
        updated = await get_async_db().users.find_one_and_update(
            {"_id": user["_id"]}, {"$set": changes}, return_document=ReturnDocument.AFTER
        )
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    return user_out(updated)


@router.post("/me/password", response_model=TokenOut)
async def change_password(body: PasswordChangeIn, response: Response, user: dict = Depends(get_current_user)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    # Bumping token_version logs out every other device; this device gets fresh tokens.
    updated = await get_async_db().users.find_one_and_update(
        {"_id": user["_id"]},
        {
            "$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.now(timezone.utc)},
            "$inc": {"token_version": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    return token_response(response, updated)
