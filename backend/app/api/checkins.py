from __future__ import annotations

import datetime as dt
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import NowDep, SessionDep, UserDep
from app.core.clock import local_date
from app.schemas.checkins import CheckInCreate, CheckInOut, CheckInPatch
from app.schemas.predictions import CheckInResult
from app.services import checkins as svc
from app.services.support import build_support, support_reasons
from app.services.twin import generate_prediction, prediction_to_out, score_date

router = APIRouter(prefix="/checkins", tags=["checkins"])


def _http(e: svc.CheckInError) -> HTTPException:
    return HTTPException(e.status_code, e.message)


@router.post("", response_model=CheckInResult)
async def create_checkin(
    data: CheckInCreate, user: UserDep, session: SessionDep, now: NowDep, response: Response
) -> CheckInResult:
    """Create or replace the check-in for a local date (defaults to today).

    Scores the stored forecast for that day, then refreshes tomorrow's forecast with the
    active model (no retraining on this path).
    """
    try:
        checkin, created = await svc.upsert_checkin(session, user, data, now)
    except svc.CheckInError as e:
        raise _http(e) from None
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    scored = await score_date(session, user, checkin.date, checkin)
    today = local_date(user.timezone, now)
    tomorrow = await generate_prediction(session, user, today, now)
    recent = await svc.list_checkins(session, user, checkin.date - timedelta(days=2), checkin.date)
    forecast_mood = tomorrow.mood_predicted if tomorrow is not None else None
    support = build_support(user, support_reasons(recent, checkin.date, forecast_mood))
    return CheckInResult(
        checkin=svc.to_out(checkin),
        scored_prediction=prediction_to_out(scored) if scored else None,
        forecast_tomorrow=prediction_to_out(tomorrow) if tomorrow else None,
        support=support,
    )


@router.get("", response_model=list[CheckInOut])
async def list_checkins(
    user: UserDep,
    session: SessionDep,
    from_: Annotated[dt.date | None, Query(alias="from")] = None,
    to: dt.date | None = None,
) -> list[CheckInOut]:
    return [svc.to_out(c) for c in await svc.list_checkins(session, user, from_, to)]


@router.get("/{day}", response_model=CheckInOut)
async def get_checkin(day: dt.date, user: UserDep, session: SessionDep) -> CheckInOut:
    c = await svc.get_checkin(session, user, day)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No check-in for that day.")
    return svc.to_out(c)


@router.patch("/{day}", response_model=CheckInOut)
async def patch_checkin(
    day: dt.date, patch: CheckInPatch, user: UserDep, session: SessionDep, now: NowDep
) -> CheckInOut:
    try:
        c = await svc.patch_checkin(session, user, day, patch)
    except svc.CheckInError as e:
        raise _http(e) from None
    await score_date(session, user, day, c)
    today = local_date(user.timezone, now)
    if day == today:
        await generate_prediction(session, user, today, now)
    return svc.to_out(c)


@router.delete("/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checkin(day: dt.date, user: UserDep, session: SessionDep) -> Response:
    if not await svc.delete_checkin(session, user, day):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No check-in for that day.")
    await score_date(session, user, day, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
