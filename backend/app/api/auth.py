from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.rate_limit import limit_auth, limit_refresh
from app.core.security import TokenError, create_token, decode_token
from app.db.models import User
from app.schemas.auth import LoginIn, SignupIn, TokenOut, UserOut
from app.schemas.common import Message
from app.services.users import EmailTakenError, authenticate, create_user

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "digibuddy_refresh"
REFRESH_PATH = "/api/v1/auth"


def _issue(response: Response, user: User) -> TokenOut:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        create_token(user.id, "refresh", user.token_version),
        max_age=s.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,  # type: ignore[arg-type]
        path=REFRESH_PATH,
    )
    return TokenOut(
        access_token=create_token(user.id, "access", user.token_version),
        expires_in=s.access_token_ttl_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/signup",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_auth)],
)
async def signup(data: SignupIn, response: Response, session: SessionDep) -> TokenOut:
    try:
        user = await create_user(session, data)
    except EmailTakenError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That email already has an account."
        ) from None
    return _issue(response, user)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(limit_auth)])
async def login(data: LoginIn, response: Response, session: SessionDep) -> TokenOut:
    user = await authenticate(session, data.email, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is not right.")
    return _issue(response, user)


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(limit_refresh)])
async def refresh(
    response: Response,
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenOut:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in again.")
    if not token:
        raise unauthorized
    try:
        payload = decode_token(token, "refresh")
        user = await session.get(User, int(payload["sub"]))
    except (TokenError, KeyError, ValueError):
        raise unauthorized from None
    if user is None or payload.get("ver", 0) != user.token_version:
        raise unauthorized
    return _issue(response, user)


@router.post("/logout", response_model=Message)
async def logout(
    response: Response,
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Message:
    """Clears the refresh cookie and revokes every token issued to this user."""
    if token:
        try:
            payload = decode_token(token, "refresh")
            user = await session.get(User, int(payload["sub"]))
            if user is not None and payload.get("ver", 0) == user.token_version:
                user.token_version += 1
                await session.commit()
        except (TokenError, KeyError, ValueError):
            pass
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return Message(detail="Signed out.")
