from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import Field

from app.schemas.checkins import CheckInOut
from app.schemas.common import APIModel


class FactorOut(APIModel):
    feature: str
    label: str
    note: str
    direction: Literal["up", "down"]
    contribution: float


class TargetForecastOut(APIModel):
    predicted: float
    lower: float
    upper: float
    actual: float | None = None
    abs_error: float | None = None
    model_type: str | None = None
    factors: list[FactorOut] = Field(default_factory=list)


class ForecastOut(APIModel):
    target_date: dt.date
    stage: int
    days_since_last_log: int
    created_at: dt.datetime | None = None
    mood: TargetForecastOut
    energy: TargetForecastOut
    stress: TargetForecastOut


class SupportResourceOut(APIModel):
    name: str
    phone: str | None
    url: str | None
    hours: str | None


class SupportOut(APIModel):
    message: str
    region: str
    reasons: list[Literal["very_low_mood", "low_mood_streak", "low_forecast"]]
    resources: list[SupportResourceOut]


class TomorrowOut(APIModel):
    status: Literal["collecting", "ready"]
    days_logged: int
    days_needed: int
    forecast: ForecastOut | None = None
    support: SupportOut | None = None


class CheckInResult(APIModel):
    checkin: CheckInOut
    scored_prediction: ForecastOut | None = None
    forecast_tomorrow: ForecastOut | None = None
    support: SupportOut | None = None


class PredictionHistoryOut(APIModel):
    items: list[ForecastOut]
