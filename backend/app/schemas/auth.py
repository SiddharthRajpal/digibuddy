from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.clock import is_valid_timezone
from app.schemas.common import APIModel


class UserOut(APIModel):
    id: int
    email: EmailStr
    display_name: str
    timezone: str
    onboarding_completed: bool
    created_at: datetime


class SignupIn(APIModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        if not is_valid_timezone(v):
            raise ValueError("Unknown timezone")
        return v


class LoginIn(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserPatch(APIModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    onboarding_completed: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_timezone(v):
            raise ValueError("Unknown timezone")
        return v
