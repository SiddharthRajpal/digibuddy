from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import APIModel


class MetricIn(APIModel):
    name: str = Field(min_length=1, max_length=60)
    min: float
    max: float
    unit: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _range(self) -> MetricIn:
        if self.max <= self.min:
            raise ValueError("max must be greater than min")
        return self


class MetricPatch(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    min: float | None = None
    max: float | None = None
    unit: str | None = Field(default=None, max_length=20)


class MetricOut(APIModel):
    id: int
    name: str
    min: float
    max: float
    unit: str | None


class TargetModelOut(APIModel):
    model_type: str | None
    trained_at: dt.datetime | None
    backtest_mae: float | None
    naive_mae: float | None
    backtest_coverage: float | None


class TargetAccuracyOut(APIModel):
    mae_7d: float | None
    mae_30d: float | None
    naive_mae_30d: float | None
    within_1_rate: float | None
    improvement_vs_naive_pct: float | None
    interval_coverage: float | None
    n_scored: int


class AccuracyPointOut(APIModel):
    date: dt.date
    mood_abs_error: float | None
    energy_abs_error: float | None
    stress_abs_error: float | None
    mae_7d: float | None
    naive_mae_7d: float | None


class TwinOut(APIModel):
    stage: int
    stage_name: str
    days_logged: int
    days_to_next_stage: int | None
    last_trained_at: dt.datetime | None
    in_tune_pct: float | None
    models: dict[str, TargetModelOut]
    accuracy: dict[str, TargetAccuracyOut]
    series: list[AccuracyPointOut]


class InsightOut(APIModel):
    kind: Literal["correlation", "weekday", "tag"]
    factor: str
    text: str
    note: str
    direction: Literal["higher", "lower"]
    n: int
    effect: float
    r: float | None = None


class InsightsOut(APIModel):
    items: list[InsightOut]
    days_logged: int
    message: str | None = None


class MetaOut(APIModel):
    name: str
    version: str
    disclaimer: str
    support_regions: list[str]


class HealthOut(APIModel):
    status: Literal["ok"]


class ExportOut(APIModel):
    exported_at: dt.datetime
    user: dict[str, Any]
    checkins: list[dict[str, Any]]
    custom_metrics: list[dict[str, Any]]
    predictions: list[dict[str, Any]]
    model_versions: list[dict[str, Any]]
