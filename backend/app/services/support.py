"""Wellbeing safety: decide when to show gentle support and which resources."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

from app.core.config import get_settings
from app.core.support_resources import SUPPORT_MESSAGE, region_for_timezone, resources_for_region
from app.db.models import DailyCheckIn, User
from app.schemas.predictions import SupportOut, SupportResourceOut

Reason = Literal["very_low_mood", "low_mood_streak", "low_forecast"]

VERY_LOW_MOOD = 2
LOW_MOOD = 3
LOW_STREAK_DAYS = 3
LOW_FORECAST = 3.0


def support_reasons(
    checkins: Sequence[DailyCheckIn], as_of: date | None, forecast_mood: float | None
) -> list[Reason]:
    """Reasons to show support.

    - The check-in on ``as_of`` has mood <= 2.
    - Mood <= 3 on each of the 3 consecutive days ending on ``as_of``.
    - The forecast for the next day predicts mood <= 3.
    """
    reasons: list[Reason] = []
    by_date = {c.date: c for c in checkins}
    if as_of is not None and as_of in by_date:
        if by_date[as_of].mood <= VERY_LOW_MOOD:
            reasons.append("very_low_mood")
        streak = [by_date.get(as_of - timedelta(days=k)) for k in range(LOW_STREAK_DAYS)]
        if all(c is not None and c.mood <= LOW_MOOD for c in streak):
            reasons.append("low_mood_streak")
    if forecast_mood is not None and forecast_mood <= LOW_FORECAST:
        reasons.append("low_forecast")
    return reasons


def build_support(user: User, reasons: list[Reason]) -> SupportOut | None:
    if not reasons:
        return None
    region = region_for_timezone(user.timezone, get_settings().default_support_region)
    return SupportOut(
        message=SUPPORT_MESSAGE,
        region=region,
        reasons=reasons,
        resources=[SupportResourceOut(**r) for r in resources_for_region(region)],
    )
