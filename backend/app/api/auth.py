from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pymongo.errors import DuplicateKeyError

from app.api.serializers import user_out
from app.core.config import get_settings
from app.core.deps import parse_object_id
from app.core.rate_limit import auth_limiter
from app.core.security import (
    REFRESH_TTL,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.mongo import get_async_db
from app.models.schemas import LoginIn, RegisterIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, user: dict) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(str(user["_id"]), user.get("token_version", 0)),
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=True,
        secure=get_settings().app_env != "development",
        samesite="lax",
        path="/api/auth",
    )


def token_response(response: Response, user: dict) -> dict:
    _set_refresh_cookie(response, user)
    return {
        "access_token": create_access_token(str(user["_id"]), user["role"], user.get("token_version", 0)),
        "user": user_out(user),
    }


@router.post("/register", response_model=TokenOut, status_code=201, dependencies=[Depends(auth_limiter)])
async def register(body: RegisterIn, response: Response):
    now = datetime.now(timezone.utc)
    user = {
        "name": body.name.strip(),
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "role": "student",  # admins are created only with scripts/create_admin.py
        "status": "active",
        "storage_used_bytes": 0,
        "token_version": 0,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await get_async_db().users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user["_id"] = result.inserted_id
    return token_response(response, user)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(auth_limiter)])
async def login(body: LoginIn, response: Response):
    user = await get_async_db().users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if user.get("status") != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    return token_response(response, user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response):
    token = request.cookies.get(REFRESH_COOKIE)
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please log in again")
    if not token:
        raise unauthorized
    try:
        payload = decode_token(token, "refresh")
    except jwt.PyJWTError:
        raise unauthorized
    user = await get_async_db().users.find_one({"_id": parse_object_id(payload["sub"])})
    if not user or user.get("token_version", 0) != payload.get("tv") or user.get("status") != "active":
        raise unauthorized
    return token_response(response, user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
