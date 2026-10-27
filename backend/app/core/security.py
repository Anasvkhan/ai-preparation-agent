from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=7)
ALGORITHM = "HS256"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _encode(payload: dict, secret: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({**payload, "iat": now, "exp": now + ttl}, secret, algorithm=ALGORITHM)


def create_access_token(user_id: str, role: str, token_version: int) -> str:
    return _encode({"sub": user_id, "role": role, "tv": token_version, "type": "access"},
                   get_settings().jwt_secret, ACCESS_TTL)


def create_refresh_token(user_id: str, token_version: int) -> str:
    return _encode({"sub": user_id, "tv": token_version, "type": "refresh"},
                   get_settings().jwt_refresh_secret, REFRESH_TTL)


def decode_token(token: str, kind: str) -> dict:
    """Raises jwt.PyJWTError if invalid/expired or the wrong kind of token."""
    s = get_settings()
    secret = s.jwt_secret if kind == "access" else s.jwt_refresh_secret
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if payload.get("type") != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return payload
