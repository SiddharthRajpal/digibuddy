"""Prediction engine tests: leakage, stages, promotion, recovery, intervals, gaps."""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.ml.data import records_to_daily
from app.ml.evaluation import conformal_halfwidth, sequential_coverage
from app.ml.features import build_features, fit_feature_spec
from app.ml.predict import forecast_next_day
from app.ml.schema import TARGETS, stage_for_days
from app.ml.training import (
    TrainConfig,
    artifact_payload,
    evaluate_candidate,
    prepare,
    train_user,
)
from scripts.generate_synthetic import generate_user

START = date(2026, 1, 1)


@cache
def synthetic(profile: str, seed: int = 0, days: int = 120) -> tuple[dict[str, Any], ...]:
    return tuple(generate_user(profile, days, start=START, seed=seed))


def first_days(records: tuple[dict[str, Any], ...], n_days: int) -> list[dict[str, Any]]:
    return [r for r in records if (r["date"] - START).days < n_days]


def first_logged(records: tuple[dict[str, Any], ...], n_logged: int) -> list[dict[str, Any]]:
    return list(records[:n_logged])


# --- leakage -----------------------------------------------------------------------------


def test_no_feature_uses_future_data() -> None:
    """Features for origin t are identical whether or not t+1 and later exist."""
    recs = synthetic("strong")
    full = records_to_daily(recs)
    spec = fit_feature_spec(records_to_daily(first_days(recs, 60)))
    X_full = build_features(full, spec)
    for cut in (20, 45, 59, 90):
        t = pd.Timestamp(START + timedelta(days=cut))
        truncated = full[full.index <= t]
        X_trunc = build_features(truncated, spec)
        pd.testing.assert_series_equal(
            X_full.loc[t], X_trunc.loc[t], check_names=False, rtol=1e-9, atol=1e-9
        )


def test_leakage_check_would_catch_a_leaky_feature() -> None:
    """Sanity check of the test itself: a deliberately leaky feature differs."""
    recs = synthetic("strong")
    full = records_to_daily(recs)
    t = pd.Timestamp(START + timedelta(days=45))
    leaky_full = full["mood"].shift(-1).loc[t]
    leaky_trunc = full[full.index <= t]["mood"].shift(-1).loc[t]
    assert not (pd.isna(leaky_full) and pd.isna(leaky_trunc))
    assert leaky_full != leaky_trunc


# --- stages ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "stage"), [(0, 0), (6, 0), (7, 1), (20, 1), (21, 2), (59, 2), (60, 3), (120, 3)]
)
def test_stage_thresholds(days: int, stage: int) -> None:
    assert stage_for_days(days) == stage


@pytest.mark.parametrize(
    ("n_logged", "stage"), [(6, 0), (7, 1), (20, 1), (21, 2), (59, 2), (60, 3)]
)
def test_stage_counts_distinct_logged_days_not_calendar_days(n_logged: int, stage: int) -> None:
    recs = first_logged(synthetic("strong"), n_logged)  # has skipped days in between
    daily = records_to_daily(recs)
    assert int(daily["logged"].sum()) == n_logged
    if n_logged >= 20:
        assert len(daily) > n_logged  # skipped days: calendar span is longer
    out = train_user(daily, cfg=TrainConfig(use_lightgbm=False))
    assert out.stage == stage
    assert (len(out.decisions) == 3) == (stage > 0)


# --- promotion rule ----------------------------------------------------------------------


def _random_walk(days: int = 90, seed: int = 3) -> list[dict[str, Any]]:
    """Mood is a bounded random walk: tomorrow = today is the best possible forecast."""
    rng = np.random.default_rng(seed)
    level = 5.5
    out = []
    for i in range(days):
        level = float(np.clip(level + rng.choice([-1, 0, 1], p=[0.3, 0.4, 0.3]), 2, 9))
        v = round(level)
        out.append(
            {
                "date": START + timedelta(days=i),
                "mood": v,
                "energy": v,
                "stress": 11 - v,
                "anxiety": 5,
                "focus": 5,
                "sleep_hours": float(rng.normal(7, 1)),
            }
        )
    return out


def test_model_worse_than_naive_is_never_activated() -> None:
    daily = records_to_daily(_random_walk())
    out = train_user(daily, {t: "ridge" for t in TARGETS}, TrainConfig(use_lightgbm=False))
    for t, d in out.decisions.items():
        w = d.winner
        assert w.model_type == "naive" or w.mae < d.naive_mae, (t, w.model_type, w.mae)


def test_active_model_kept_unless_challenger_clearly_wins() -> None:
    recs = first_logged(synthetic("strong", seed=1), 75)
    cfg = TrainConfig(use_lightgbm=False)
    out = train_user(records_to_daily(recs), {t: "baseline" for t in TARGETS}, cfg)
    for d in out.decisions.values():
        if d.winner.model_type != "baseline":
            # A switch only happens with a clear win over both references.
            assert d.winner.mae < d.candidates["baseline"].mae * (1 - cfg.min_improvement)
            assert d.winner.mae < d.naive_mae * (1 - cfg.min_improvement)
            assert d.reason.startswith("promoted")
        else:
            assert d.reason.startswith(("kept", "refreshed"))


# --- synthetic recovery ------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize(("n_days", "types"), [(66, ("ridge",)), (120, ("ridge", "gbm"))])
def test_strong_signal_models_beat_naive_by_15_percent(n_days: int, types: tuple[str, ...]) -> None:
    """Stage 2 (ridge) and stage 3 models beat naive persistence MAE by at least 15%."""
    recs = first_days(synthetic("strong"), n_days)
    cfg = TrainConfig()
    _, X, Y, rows = prepare(records_to_daily(recs), cfg)
    Xr = X.loc[rows]
    expected_stage = 2 if n_days < 70 else 3
    assert stage_for_days(len(recs)) == expected_stage
    for target in TARGETS:
        y = Y.loc[rows, target]
        naive = evaluate_candidate("naive", target, Xr, y, cfg, 30).mae
        best = min(evaluate_candidate(t, target, Xr, y, cfg, 30).mae for t in types)
        assert best <= 0.85 * naive, (target, best, naive)


@pytest.mark.slow
@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_pure_noise_user_is_not_promoted_beyond_baseline(seed: int) -> None:
    """On 120 days of noise, neither ridge nor gbm is promoted over the baseline."""
    daily = records_to_daily(synthetic("noise", seed))
    out = train_user(daily, {t: "baseline" for t in TARGETS})
    assert out.stage == 3
    for t, d in out.decisions.items():
        assert d.winner.model_type in ("naive", "baseline"), (t, d.winner.model_type, d.reason)


# --- intervals ---------------------------------------------------------------------------


def test_conformal_halfwidth_basics() -> None:
    r = np.arange(1, 11, dtype=float)  # |residuals| 1..10
    assert conformal_halfwidth(r, 0.8) == 9.0  # ceil(11 * 0.8) = 9th smallest
    assert conformal_halfwidth(r[:3], 0.8) == 1.5  # too few residuals -> default


@pytest.mark.slow
def test_interval_coverage_close_to_80_percent() -> None:
    """Empirical 80% interval coverage on synthetic data lies between 70% and 90%."""
    cfg = TrainConfig()
    hits: list[float] = []
    for profile, seed in (("strong", 0), ("weak", 0), ("strong", 2)):
        _, X, Y, rows = prepare(records_to_daily(synthetic(profile, seed)), cfg)
        Xr = X.loc[rows]
        for target in TARGETS:
            res = evaluate_candidate("ridge", target, Xr, Y.loc[rows, target], cfg, 60)
            cov = sequential_coverage(res.backtest.residuals, cfg.coverage)
            assert cov is not None
            hits.append(cov)
    coverage = float(np.mean(hits))
    assert 0.70 <= coverage <= 0.90, coverage


# --- gaps and missing values -------------------------------------------------------------


def _forecast(recs: list[dict[str, Any]], origin: date, model: str = "ridge") -> Any:
    daily = records_to_daily(recs)
    out = train_user(daily, {t: model for t in TARGETS}, TrainConfig(use_lightgbm=False))
    artifacts = {t: artifact_payload(out, t) for t in TARGETS}
    return forecast_next_day(records_to_daily(recs, through=origin), origin, artifacts)


def test_predictions_valid_with_skipped_days_and_nulls() -> None:
    recs = [dict(r) for r in first_days(synthetic("weak", seed=4), 70)]
    rng = np.random.default_rng(0)
    for r in recs:  # very patchy optional data
        for f in ("sleep_hours", "workload", "exercise_minutes", "social_interaction"):
            if rng.random() < 0.5:
                r[f] = None
    last = recs[-1]["date"]
    fc = _forecast(recs, last)
    for t in TARGETS:
        tf = fc.targets[t]
        assert np.isfinite(tf.predicted)
        assert 1 <= tf.lower <= tf.predicted <= tf.upper <= 10
        assert len(tf.factors) >= 1


def test_gap_widens_interval_and_long_gap_reverts_to_baseline() -> None:
    recs = first_days(synthetic("strong"), 70)
    last = recs[-1]["date"]
    fresh = _forecast(recs, last)
    gap2 = _forecast(recs, last + timedelta(days=2))
    gap5 = _forecast(recs, last + timedelta(days=5))
    assert fresh.days_since_last_log == 0
    assert gap2.days_since_last_log == 2 and not gap2.reverted_to_baseline
    assert gap5.days_since_last_log == 5 and gap5.reverted_to_baseline
    for t in TARGETS:
        w_fresh = fresh.targets[t].upper - fresh.targets[t].lower
        w_gap5 = gap5.targets[t].upper - gap5.targets[t].lower
        assert gap5.targets[t].model_type == "baseline"
        assert w_gap5 >= w_fresh - 1e-9
