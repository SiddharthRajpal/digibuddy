from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.security import TokenError, decode_token
from app.db.models import User
from app.db.session import get_session

bearer = HTTPBearer(auto_error=False)


async def db_session() -> AsyncIterator[AsyncSession]:
    async for s in get_session():
        yield s


def get_now() -> datetime:
    """Current UTC time. Overridden in tests."""
    return utcnow()


SessionDep = Annotated[AsyncSession, Depends(db_session)]
NowDep = Annotated[datetime, Depends(get_now)]


async def current_user(
    request: Request,
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Please sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        payload = decode_token(creds.credentials, "access")
        user_id = int(payload["sub"])
    except (TokenError, KeyError, ValueError):
        raise unauthorized from None
    user = await session.get(User, user_id)
    if user is None or payload.get("ver", 0) != user.token_version:
        raise unauthorized
    request.state.user_id = user.id
    return user


UserDep = Annotated[User, Depends(current_user)]
