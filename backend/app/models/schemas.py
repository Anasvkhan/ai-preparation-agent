from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def _check_password(v: str) -> str:
    if len(v) < 8 or not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
        raise ValueError("Password must be at least 8 characters and contain letters and numbers")
    return v


# ---- Auth / users ----
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(max_length=128)

    _pw = field_validator("password")(_check_password)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    storage_used_bytes: int
    quota_bytes: int
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    email: EmailStr | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(_check_password)


# ---- Projects ----
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class ProjectOut(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
