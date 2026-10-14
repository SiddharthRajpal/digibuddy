"""Produce a next-day forecast from trained artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.ml.data import extend_to
from app.ml.evaluation import DEFAULT_HALFWIDTH, clip_round, widen_for_gap
from app.ml.features import FeatureSpec, build_features
from app.ml.models import BaselineModel, ForecastModel
from app.ml.schema import TARGETS


@dataclass
class TargetForecast:
    predicted: float
    lower: float
    upper: float
    naive: float | None
    model_type: str
    factors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Forecast:
    target_date: date
    days_since_last_log: int
    reverted_to_baseline: bool
    targets: dict[str, TargetForecast]


def _artifact_model(artifact: dict[str, Any] | None, target: str) -> tuple[ForecastModel, float]:
    if artifact is None or artifact.get("model") is None:
        return BaselineModel(target), DEFAULT_HALFWIDTH
    return artifact["model"], float(artifact["halfwidth"])


def forecast_next_day(
    daily: pd.DataFrame,
    origin: date,
    artifacts: dict[str, dict[str, Any] | None],
    gap_revert_days: int = 3,
    custom_names: dict[str, str] | None = None,
    baseline_half_life_days: float = 3.0,
) -> Forecast:
    """Forecast ``origin + 1`` using data up to and including ``origin``.

    If the user has not logged for more than ``gap_revert_days`` days, every target
    falls back to the stage 1 baseline, with an interval widened for the gap.
    """
    cal = extend_to(daily, origin)
    spec: FeatureSpec | None = None
    for a in artifacts.values():
        if a and a.get("spec") is not None:
            spec = a["spec"]
            break
    spec = spec or FeatureSpec(baseline_half_life_days=baseline_half_life_days)
    X = build_features(cal, spec)
    x = X.loc[[pd.Timestamp(origin)]]
    days_since = int(x["days_since_last_log"].iloc[0])
    revert = days_since > gap_revert_days

    out: dict[str, TargetForecast] = {}
    for target in TARGETS:
        model, q = _artifact_model(artifacts.get(target), target)
        if revert:
            model = BaselineModel(target)
        point = float(model.predict(x)[0])
        if not np.isfinite(point):
            point = float(BaselineModel(target).predict(x)[0])
        hw = widen_for_gap(q, days_since)
        pred = float(clip_round(point))
        lo = float(clip_round(point - hw))
        hi = float(clip_round(point + hw))
        naive = x[f"{target}_lag0"].iloc[0]
        factors = [f.as_dict(custom_names) for f in model.explain(x)]
        out[target] = TargetForecast(
            predicted=pred,
            lower=lo,
            upper=hi,
            naive=None if pd.isna(naive) else float(naive),
            model_type=model.model_type,
            factors=factors,
        )
    return Forecast(
        target_date=origin + timedelta(days=1),
        days_since_last_log=days_since,
        reverted_to_baseline=revert,
        targets=out,
    )
