from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from fastapi.responses import PlainTextResponse

from app.api.auth import REFRESH_COOKIE, REFRESH_PATH
from app.api.deps import SessionDep, UserDep
from app.schemas.auth import UserOut, UserPatch
from app.schemas.misc import ExportOut
from app.services.users import delete_user, export_checkins_csv, export_user, update_user

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(user: UserDep) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("", response_model=UserOut)
async def patch_me(patch: UserPatch, user: UserDep, session: SessionDep) -> UserOut:
    return UserOut.model_validate(await update_user(session, user, patch))


@router.get(
    "/export",
    response_model=ExportOut,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export(
    user: UserDep, session: SessionDep, format: Literal["json", "csv"] = "json"
) -> ExportOut | PlainTextResponse:
    """All of your data as JSON, or your check-ins as CSV with ``?format=csv``."""
    if format == "csv":
        return PlainTextResponse(
            await export_checkins_csv(session, user),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="digibuddy-checkins.csv"'},
        )
    return ExportOut(**await export_user(session, user))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: UserDep, session: SessionDep, response: Response) -> Response:
    """Permanently delete the account, all data, and all trained model files."""
    await delete_user(session, user)
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    out.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return out
