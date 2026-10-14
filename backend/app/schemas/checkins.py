from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import Field, field_validator

from app.schemas.common import APIModel

Feeling = Annotated[int, Field(ge=1, le=10)]
Scale5 = Annotated[int, Field(ge=1, le=5)]
Tag = Annotated[str, Field(min_length=1, max_length=32)]


class MetricValueIn(APIModel):
    metric_id: int
    value: float


class MetricValueOut(APIModel):
    metric_id: int
    value: float


class _OptionalFields(APIModel):
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_quality: Scale5 | None = None
    exercise_minutes: int | None = Field(default=None, ge=0, le=1440)
    outdoor_minutes: int | None = Field(default=None, ge=0, le=1440)
    screen_time_hours: float | None = Field(default=None, ge=0, le=24)
    caffeine_servings: int | None = Field(default=None, ge=0, le=50)
    alcohol_units: int | None = Field(default=None, ge=0, le=100)
    meals_eaten: int | None = Field(default=None, ge=0, le=5)
    social_interaction: Scale5 | None = None
    workload: Scale5 | None = None
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v: list[str]) -> list[str]:
        seen: list[str] = []
        for t in v:
            t2 = t.strip().lower()
            if t2 and t2 not in seen:
                seen.append(t2)
        return seen


class CheckInCreate(_OptionalFields):
    """Create or replace the check-in for a local date (defaults to today)."""

    date: dt.date | None = None
    mood: Feeling
    energy: Feeling
    stress: Feeling
    anxiety: Feeling
    focus: Feeling
    custom_metrics: list[MetricValueIn] = Field(default_factory=list)


class CheckInPatch(APIModel):
    mood: Feeling | None = None
    energy: Feeling | None = None
    stress: Feeling | None = None
    anxiety: Feeling | None = None
    focus: Feeling | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_quality: Scale5 | None = None
    exercise_minutes: int | None = Field(default=None, ge=0, le=1440)
    outdoor_minutes: int | None = Field(default=None, ge=0, le=1440)
    screen_time_hours: float | None = Field(default=None, ge=0, le=24)
    caffeine_servings: int | None = Field(default=None, ge=0, le=50)
    alcohol_units: int | None = Field(default=None, ge=0, le=100)
    meals_eaten: int | None = Field(default=None, ge=0, le=5)
    social_interaction: Scale5 | None = None
    workload: Scale5 | None = None
    tags: list[Tag] | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)
    custom_metrics: list[MetricValueIn] | None = None


class CheckInOut(APIModel):
    id: int
    date: dt.date
    mood: int
    energy: int
    stress: int
    anxiety: int
    focus: int
    sleep_hours: float | None
    sleep_quality: int | None
    exercise_minutes: int | None
    outdoor_minutes: int | None
    screen_time_hours: float | None
    caffeine_servings: int | None
    alcohol_units: int | None
    meals_eaten: int | None
    social_interaction: int | None
    workload: int | None
    tags: list[str]
    notes: str | None
    custom_metrics: list[MetricValueOut] = Field(default_factory=list)
    created_at: dt.datetime
    updated_at: dt.datetime
