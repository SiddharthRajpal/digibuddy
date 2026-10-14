"""Rolling-origin backtesting and split-conformal prediction intervals."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.ml.models import ForecastModel, recency_weights
from app.ml.schema import VALUE_MAX, VALUE_MIN

MIN_CONFORMAL_RESIDUALS = 5
DEFAULT_HALFWIDTH = 1.5
MIN_HALFWIDTH = 0.5


@dataclass
class BacktestResult:
    dates: pd.DatetimeIndex
    predictions: np.ndarray
    actuals: np.ndarray
    naive: np.ndarray

    @property
    def residuals(self) -> np.ndarray:
        return np.asarray(self.actuals - self.predictions, dtype=float)

    @property
    def mae(self) -> float:
        return float(np.mean(np.abs(self.residuals))) if len(self.actuals) else math.nan

    @property
    def naive_mae(self) -> float:
        return float(np.mean(np.abs(self.actuals - self.naive))) if len(self.actuals) else math.nan


def clip_round(values: np.ndarray | float) -> np.ndarray:
    out: np.ndarray = np.round(np.clip(np.asarray(values, dtype=float), VALUE_MIN, VALUE_MAX), 1)
    return out


def backtest_window(n_rows: int, max_days: int, fraction: float, fitted: bool) -> int:
    """How many of the most recent rows to backtest on.

    Models that are not fitted (naive, baseline) make honest out-of-sample predictions
    on every row, so they can use the full ``max_days`` window from the start.
    """
    if n_rows <= 0:
        return 0
    if not fitted:
        return min(max_days, n_rows)
    return max(1, min(max_days, int(fraction * n_rows)))


def rolling_origin_backtest(
    model_factory: Callable[[], ForecastModel],
    X: pd.DataFrame,
    y: pd.Series,
    n_test: int,
    half_life_days: float,
    min_train: int = 10,
) -> BacktestResult:
    """Expanding-window backtest over the last ``n_test`` rows of ``X``.

    For each test origin ``t`` the model is trained only on rows whose target day is
    on or before ``t`` (origin ``< t``), then predicts ``t + 1``.
    """
    target = model_factory().target
    n = len(X)
    test_idx = np.arange(max(0, n - n_test), n)
    preds = np.empty(len(test_idx))
    proto = model_factory()
    if not proto.needs_fit:
        preds = proto.predict(X.iloc[test_idx])
    else:
        for j, i in enumerate(test_idx):
            if i < min_train:
                # Not enough history to fit: fall back to the baseline's logic.
                row = X.iloc[[int(i)]]
                preds[j] = float(
                    row[f"base_ewma_{target}"].iloc[0] + row[f"base_dowoff_{target}"].iloc[0]
                )
                continue
            Xtr, ytr = X.iloc[:i], y.iloc[:i].to_numpy(dtype=float)
            w = recency_weights(Xtr.index, half_life_days)
            m = model_factory().fit(Xtr, ytr, w)
            preds[j] = float(m.predict(X.iloc[[int(i)]])[0])
    preds = np.clip(preds, VALUE_MIN, VALUE_MAX)
    naive = X[f"{target}_lag0"].iloc[test_idx].to_numpy(dtype=float)
    return BacktestResult(
        dates=pd.DatetimeIndex(X.index[test_idx]),
        predictions=preds,
        actuals=y.iloc[test_idx].to_numpy(dtype=float),
        naive=naive,
    )


def conformal_halfwidth(residuals: np.ndarray, coverage: float = 0.8) -> float:
    """Split-conformal half-width: the ceil((n+1)·coverage)-th smallest |residual|."""
    r = np.sort(np.abs(np.asarray(residuals, dtype=float)))
    n = len(r)
    if n < MIN_CONFORMAL_RESIDUALS:
        return DEFAULT_HALFWIDTH
    k = math.ceil((n + 1) * coverage)
    q = float(r[min(k, n) - 1])
    return max(q, MIN_HALFWIDTH)


def sequential_coverage(residuals: np.ndarray, coverage: float = 0.8) -> float | None:
    """Empirical coverage when each interval is calibrated only on earlier residuals."""
    r = np.abs(np.asarray(residuals, dtype=float))
    hits: list[bool] = []
    for j in range(MIN_CONFORMAL_RESIDUALS, len(r)):
        hits.append(bool(r[j] <= conformal_halfwidth(r[:j], coverage)))
    return float(np.mean(hits)) if hits else None


def widen_for_gap(halfwidth: float, days_since_last_log: float) -> float:
    """Wider intervals when today's check-in is missing (stale information)."""
    extra = max(0.0, float(days_since_last_log) - 1.0)
    return halfwidth * (1.0 + 0.25 * extra)
