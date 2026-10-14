"""Check-in CRUD. Every query is scoped to the calling user (authorization lives here)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import local_date
from app.db.models import CustomMetric, CustomMetricValue, DailyCheckIn, User
from app.ml.schema import CORE_FEELINGS, OPTIONAL_NUMERIC
from app.schemas.checkins import (
    CheckInCreate,
    CheckInOut,
    CheckInPatch,
    MetricValueIn,
    MetricValueOut,
)

BACKFILL_DAYS = 3


class CheckInError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_create_date(user: User, requested: date | None, now: datetime) -> date:
    today = local_date(user.timezone, now)
    d = requested or today
    if d > today:
        raise CheckInError("You can't check in for a future day.")
    if d < today - timedelta(days=BACKFILL_DAYS):
        raise CheckInError(f"You can only fill in the last {BACKFILL_DAYS} days.")
    return d


async def _validate_metrics(
    session: AsyncSession, user: User, values: list[MetricValueIn]
) -> dict[int, float]:
    if not values:
        return {}
    metrics = {
        m.id: m
        for m in (
            await session.scalars(select(CustomMetric).where(CustomMetric.user_id == user.id))
        ).all()
    }
    out: dict[int, float] = {}
    for v in values:
        m = metrics.get(v.metric_id)
        if m is None:
            raise CheckInError(f"Unknown tracker {v.metric_id}.")
        if not (m.min <= v.value <= m.max):
            raise CheckInError(f"{m.name} must be between {m.min:g} and {m.max:g}.")
        out[v.metric_id] = v.value
    return out


def _set_metric_values(checkin: DailyCheckIn, values: dict[int, float]) -> None:
    existing = {mv.metric_id: mv for mv in checkin.metric_values}
    for mid, val in values.items():
        if mid in existing:
            existing[mid].value = val
        else:
            checkin.metric_values.append(CustomMetricValue(metric_id=mid, value=val))


async def get_checkin(session: AsyncSession, user: User, d: date) -> DailyCheckIn | None:
    return await session.scalar(
        select(DailyCheckIn)
        .options(selectinload(DailyCheckIn.metric_values))
        .where(DailyCheckIn.user_id == user.id, DailyCheckIn.date == d)
    )


async def upsert_checkin(
    session: AsyncSession, user: User, data: CheckInCreate, now: datetime
) -> tuple[DailyCheckIn, bool]:
    d = validate_create_date(user, data.date, now)
    metric_values = await _validate_metrics(session, user, data.custom_metrics)
    checkin = await get_checkin(session, user, d)
    created = checkin is None
    fields = data.model_dump(exclude={"date", "custom_metrics"})
    if checkin is None:
        checkin = DailyCheckIn(user_id=user.id, date=d, **fields)
        checkin.metric_values = []
        session.add(checkin)
    else:
        for k, v in fields.items():
            setattr(checkin, k, v)
    _set_metric_values(checkin, metric_values)
    await session.commit()
    refreshed = await get_checkin(session, user, d)
    assert refreshed is not None
    return refreshed, created


async def patch_checkin(
    session: AsyncSession, user: User, d: date, patch: CheckInPatch
) -> DailyCheckIn:
    checkin = await get_checkin(session, user, d)
    if checkin is None:
        raise CheckInError("No check-in for that day.", status_code=404)
    data = patch.model_dump(exclude_unset=True)
    metrics = data.pop("custom_metrics", None)
    for k, v in data.items():
        if k in CORE_FEELINGS and v is None:
            raise CheckInError(f"{k} can't be empty.")
        if k == "tags" and v is None:
            v = []
        setattr(checkin, k, v)
    if metrics is not None:
        values = await _validate_metrics(session, user, [MetricValueIn(**m) for m in metrics])
        _set_metric_values(checkin, values)
    await session.commit()
    refreshed = await get_checkin(session, user, d)
    assert refreshed is not None
    return refreshed


async def delete_checkin(session: AsyncSession, user: User, d: date) -> bool:
    res = await session.execute(
        delete(DailyCheckIn).where(DailyCheckIn.user_id == user.id, DailyCheckIn.date == d)
    )
    await session.commit()
    return bool(res.rowcount)  # type: ignore[attr-defined]


async def list_checkins(
    session: AsyncSession, user: User, start: date | None = None, end: date | None = None
) -> list[DailyCheckIn]:
    q = (
        select(DailyCheckIn)
        .options(selectinload(DailyCheckIn.metric_values))
        .where(DailyCheckIn.user_id == user.id)
    )
    if start is not None:
        q = q.where(DailyCheckIn.date >= start)
    if end is not None:
        q = q.where(DailyCheckIn.date <= end)
    return list((await session.scalars(q.order_by(DailyCheckIn.date))).all())


async def count_logged_days(session: AsyncSession, user: User, through: date | None = None) -> int:
    q = select(func.count(DailyCheckIn.id)).where(DailyCheckIn.user_id == user.id)
    if through is not None:
        q = q.where(DailyCheckIn.date <= through)
    return int(await session.scalar(q) or 0)


def to_out(c: DailyCheckIn) -> CheckInOut:
    return CheckInOut(
        id=c.id,
        date=c.date,
        **{f: getattr(c, f) for f in (*CORE_FEELINGS, *OPTIONAL_NUMERIC)},
        tags=list(c.tags or []),
        notes=c.notes,
        custom_metrics=[
            MetricValueOut(metric_id=mv.metric_id, value=mv.value) for mv in c.metric_values
        ],
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def to_record(c: DailyCheckIn) -> dict[str, Any]:
    """ML record. Notes are intentionally left out (never modelled in v1)."""
    rec: dict[str, Any] = {"date": c.date, "tags": list(c.tags or [])}
    for f in (*CORE_FEELINGS, *OPTIONAL_NUMERIC):
        rec[f] = getattr(c, f)
    rec["custom"] = {mv.metric_id: mv.value for mv in c.metric_values}
    return rec
