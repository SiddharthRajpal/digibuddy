"""Smaller routers: custom metrics, predictions, twin, insights, meta and health."""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import NowDep, SessionDep, UserDep
from app.core.clock import local_date
from app.core.config import get_settings
from app.core.support_resources import RESOURCES
from app.db.models import CustomMetric, Prediction
from app.ml.schema import days_needed_for_next_stage
from app.schemas.misc import (
    HealthOut,
    InsightsOut,
    MetaOut,
    MetricIn,
    MetricOut,
    MetricPatch,
    TwinOut,
)
from app.schemas.predictions import PredictionHistoryOut, TomorrowOut
from app.services.accuracy import twin_status
from app.services.checkins import count_logged_days, list_checkins
from app.services.insights import compute_insights
from app.services.support import build_support, support_reasons
from app.services.twin import (
    custom_metric_names,
    generate_prediction,
    get_prediction,
    load_daily,
    prediction_to_out,
)

DISCLAIMER = (
    "DigiBuddy is a self-reflection tool, not a medical device. It does not diagnose, "
    "treat or prevent any condition, and its forecasts are estimates, not advice. If you "
    "are struggling, please reach out to someone you trust or a support line."
)

# --- custom metrics -------------------------------------------------------------------

metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])


async def _own_metric(session: SessionDep, user: UserDep, metric_id: int) -> CustomMetric:
    m = await session.scalar(
        select(CustomMetric).where(CustomMetric.id == metric_id, CustomMetric.user_id == user.id)
    )
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracker not found.")
    return m


@metrics_router.get("", response_model=list[MetricOut])
async def list_metrics(user: UserDep, session: SessionDep) -> list[MetricOut]:
    rows = await session.scalars(
        select(CustomMetric).where(CustomMetric.user_id == user.id).order_by(CustomMetric.id)
    )
    return [MetricOut.model_validate(m) for m in rows]


@metrics_router.post("", response_model=MetricOut, status_code=status.HTTP_201_CREATED)
async def create_metric(data: MetricIn, user: UserDep, session: SessionDep) -> MetricOut:
    m = CustomMetric(user_id=user.id, **data.model_dump())
    session.add(m)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have a tracker with that name."
        ) from None
    await session.refresh(m)
    return MetricOut.model_validate(m)


@metrics_router.patch("/{metric_id}", response_model=MetricOut)
async def patch_metric(
    metric_id: int, patch: MetricPatch, user: UserDep, session: SessionDep
) -> MetricOut:
    m = await _own_metric(session, user, metric_id)
    for k, v in patch.model_dump(exclude_unset=True).items():
        if v is not None or k == "unit":
            setattr(m, k, v)
    if m.max <= m.min:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "max must be greater than min")
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have a tracker with that name."
        ) from None
    await session.refresh(m)
    return MetricOut.model_validate(m)


@metrics_router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(metric_id: int, user: UserDep, session: SessionDep) -> Response:
    m = await _own_metric(session, user, metric_id)
    await session.delete(m)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- predictions ----------------------------------------------------------------------

predictions_router = APIRouter(prefix="/predictions", tags=["predictions"])


@predictions_router.get("/tomorrow", response_model=TomorrowOut)
async def tomorrow(user: UserDep, session: SessionDep, now: NowDep) -> TomorrowOut:
    """Tomorrow's forecast, or progress toward the first one (7 logged days).

    Includes a ``support`` object whenever the latest check-in (today or yesterday) or
    the forecast calls for it, so the Today page can show it first.
    """
    today = local_date(user.timezone, now)
    n = await count_logged_days(session, user, through=today)
    recent = await list_checkins(session, user, today - timedelta(days=3), today)
    as_of = recent[-1].date if recent and recent[-1].date >= today - timedelta(days=1) else None
    if n < 7:
        support = build_support(user, support_reasons(recent, as_of, None))
        return TomorrowOut(status="collecting", days_logged=n, days_needed=7 - n, support=support)
    p = await get_prediction(session, user, today + timedelta(days=1))
    if p is None:
        p = await generate_prediction(session, user, today, now)
    support = build_support(
        user, support_reasons(recent, as_of, p.mood_predicted if p is not None else None)
    )
    return TomorrowOut(
        status="ready",
        days_logged=n,
        days_needed=0,
        forecast=prediction_to_out(p) if p is not None else None,
        support=support,
    )


@predictions_router.get("/history", response_model=PredictionHistoryOut)
async def history(
    user: UserDep,
    session: SessionDep,
    from_: Annotated[dt.date | None, Query(alias="from")] = None,
    to: dt.date | None = None,
) -> PredictionHistoryOut:
    q = select(Prediction).where(Prediction.user_id == user.id)
    if from_ is not None:
        q = q.where(Prediction.target_date >= from_)
    if to is not None:
        q = q.where(Prediction.target_date <= to)
    rows = await session.scalars(q.order_by(Prediction.target_date.desc()))
    return PredictionHistoryOut(items=[prediction_to_out(p) for p in rows])


# --- twin, insights, meta -------------------------------------------------------------

twin_router = APIRouter(tags=["twin"])


@twin_router.get("/twin", response_model=TwinOut)
async def twin(user: UserDep, session: SessionDep, now: NowDep) -> TwinOut:
    return await twin_status(session, user, local_date(user.timezone, now))


@twin_router.get("/insights", response_model=InsightsOut, tags=["insights"])
async def insights(user: UserDep, session: SessionDep) -> InsightsOut:
    daily = await load_daily(session, user)
    n = await count_logged_days(session, user)
    items = compute_insights(daily, await custom_metric_names(session, user))
    message = None
    if not items:
        needed = max(0, 22 - n)
        message = (
            f"Keep checking in. Patterns start to show after about {needed} more days."
            if needed
            else "No clear patterns yet. That's okay: your days may simply be varied."
        )
    return InsightsOut(items=items, days_logged=n, message=message)


meta_router = APIRouter(tags=["meta"])


@meta_router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status="ok")


@meta_router.get("/meta", response_model=MetaOut)
async def meta(user: UserDep) -> MetaOut:
    s = get_settings()
    return MetaOut(
        name=s.app_name,
        version=s.app_version,
        disclaimer=DISCLAIMER,
        support_regions=sorted(RESOURCES),
    )


__all__ = [
    "days_needed_for_next_stage",
    "meta_router",
    "metrics_router",
    "predictions_router",
    "twin_router",
]
