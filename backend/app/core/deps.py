"""FastAPI dependencies for authentication, roles and ownership checks."""
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.db.mongo import get_async_db

_bearer = HTTPBearer(auto_error=False)


def parse_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise unauthorized

    user = await get_async_db().users.find_one({"_id": parse_object_id(payload["sub"])})
    # token_version changes on password change / suspension -> old tokens stop working.
    if not user or user.get("token_version", 0) != payload.get("tv"):
        raise unauthorized
    if user.get("status") != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    return user


def require_role(role: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker


async def get_owned_project(project_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Returns the project only if it belongs to the current user. 404 otherwise (no ID enumeration)."""
    project = await get_async_db().projects.find_one(
        {"_id": parse_object_id(project_id), "user_id": user["_id"]}
    )
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project
