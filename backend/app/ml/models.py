"""Forecast models. Every model predicts one target for day t + 1 from the feature row of day t.

- ``naive``: persistence, tomorrow equals the last logged value. The floor every model must beat.
- ``baseline``: EWMA (half-life 3 days) plus a day-of-week offset (stage 1).
- ``ridge``: per-target ridge regression, alpha picked by time-series CV (stage 2).
- ``gbm``: gradient boosting, LightGBM if installed, else sklearn's HistGradientBoosting (stage 3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.feature_labels import describe

logger = logging.getLogger(__name__)

ModelType = Literal["naive", "baseline", "ridge", "gbm"]
RIDGE_ALPHAS = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)

try:  # optional dependency
    import lightgbm as _lgb

    HAS_LIGHTGBM = True
except Exception:  # pragma: no cover - depends on environment
    _lgb = None  # type: ignore[assignment]
    HAS_LIGHTGBM = False


@dataclass
class Factor:
    feature: str
    direction: Literal["up", "down"]
    contribution: float

    def as_dict(self, custom_names: dict[str, str] | None = None) -> dict[str, Any]:
        label, note = describe(self.feature, custom_names)
        return {
            "feature": self.feature,
            "label": label,
            "note": note,
            "direction": self.direction,
            "contribution": round(float(self.contribution), 2),
        }


def _top_factors(contribs: dict[str, float], k: int = 3) -> list[Factor]:
    # Merge features that share a human label (e.g. dow sin/cos) before ranking.
    merged: dict[str, tuple[str, float]] = {}
    for feat, c in contribs.items():
        if not np.isfinite(c) or c == 0:
            continue
        key = describe(feat)[0]
        prev = merged.get(key)
        if prev is None:
            merged[key] = (feat, c)
        else:
            merged[key] = (prev[0] if abs(prev[1]) >= abs(c) else feat, prev[1] + c)
    ranked = sorted(merged.values(), key=lambda fc: abs(fc[1]), reverse=True)[:k]
    return [Factor(f, "up" if c > 0 else "down", c) for f, c in ranked]


def recency_weights(index: pd.Index, half_life_days: float) -> np.ndarray:
    if len(index) == 0:
        return np.array([])
    ts = pd.DatetimeIndex(index)
    age = (ts.max() - ts).days.to_numpy(dtype=float)
    return np.asarray(0.5 ** (age / half_life_days), dtype=float)


class ForecastModel:
    model_type: ModelType
    needs_fit: bool = True

    def __init__(self, target: str) -> None:
        self.target = target
        self.hyperparameters: dict[str, Any] = {}
        self.features: list[str] = []

    def fit(self, X: pd.DataFrame, y: np.ndarray, w: np.ndarray | None = None) -> ForecastModel:
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:  # pragma: no cover - abstract
        raise NotImplementedError

    def explain(self, x: pd.DataFrame) -> list[Factor]:  # pragma: no cover - abstract
        raise NotImplementedError


class NaiveModel(ForecastModel):
    model_type: ModelType = "naive"
    needs_fit = False

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return X[f"{self.target}_lag0"].to_numpy(dtype=float)

    def explain(self, x: pd.DataFrame) -> list[Factor]:
        row = x.iloc[0]
        c = float(row[f"{self.target}_lag0"] - row[f"{self.target}_mean_7d"])
        return _top_factors({f"{self.target}_lag0": c if c != 0 else 1e-6})


class BaselineModel(ForecastModel):
    model_type: ModelType = "baseline"
    needs_fit = False

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        level = X[f"base_ewma_{self.target}"].to_numpy(dtype=float)
        offset = X[f"base_dowoff_{self.target}"].to_numpy(dtype=float)
        return np.asarray(level + np.nan_to_num(offset), dtype=float)

    def explain(self, x: pd.DataFrame) -> list[Factor]:
        row = x.iloc[0]
        trend = float(row[f"base_ewma_{self.target}"] - row[f"base_mean_{self.target}"])
        dow = float(row[f"base_dowoff_{self.target}"])
        return _top_factors({"recent_trend": trend, "day_of_week": dow})


class RidgeModel(ForecastModel):
    model_type: ModelType = "ridge"

    def __init__(
        self,
        target: str,
        alphas: tuple[float, ...] = RIDGE_ALPHAS,
        fixed_alpha: float | None = None,
    ) -> None:
        super().__init__(target)
        self.alphas = alphas
        self.fixed_alpha = fixed_alpha
        self.pipeline: Pipeline | None = None

    @staticmethod
    def _make(alpha: float) -> Pipeline:
        return Pipeline(
            [
                ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scale", StandardScaler()),
                ("ridge", Ridge(alpha=alpha)),
            ]
        )

    def choose_alpha(self, X: pd.DataFrame, y: np.ndarray, w: np.ndarray) -> float:
        """Pick alpha by time-series cross-validation (weighted fit, MAE score)."""
        n = len(y)
        n_splits = min(4, max(2, n // 8))
        if n < 12:
            return 100.0
        tscv = TimeSeriesSplit(n_splits=n_splits)
        best_alpha, best_err = self.alphas[-1], np.inf
        for alpha in self.alphas:
            errs: list[float] = []
            for tr, te in tscv.split(X):
                p = self._make(alpha)
                p.fit(X.iloc[tr], y[tr], ridge__sample_weight=w[tr])
                errs.append(float(np.mean(np.abs(p.predict(X.iloc[te]) - y[te]))))
            err = float(np.mean(errs))
            if err < best_err:
                best_alpha, best_err = alpha, err
        return best_alpha

    def fit(self, X: pd.DataFrame, y: np.ndarray, w: np.ndarray | None = None) -> RidgeModel:
        w = np.ones(len(y)) if w is None else w
        self.features = list(X.columns)
        alpha = self.fixed_alpha if self.fixed_alpha is not None else self.choose_alpha(X, y, w)
        self.hyperparameters = {"alpha": alpha}
        self.pipeline = self._make(alpha)
        self.pipeline.fit(X, y, ridge__sample_weight=w)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        assert self.pipeline is not None
        return np.asarray(self.pipeline.predict(X[self.features]), dtype=float)

    def explain(self, x: pd.DataFrame) -> list[Factor]:
        assert self.pipeline is not None
        z = self.pipeline[:-1].transform(x[self.features])[0]
        coef = self.pipeline.named_steps["ridge"].coef_
        contribs = {f: float(c * v) for f, c, v in zip(self.features, coef, z, strict=True)}
        return _top_factors(contribs)


class GBMModel(ForecastModel):
    model_type: ModelType = "gbm"

    def __init__(self, target: str, use_lightgbm: bool = True) -> None:
        super().__init__(target)
        self.use_lightgbm = use_lightgbm and HAS_LIGHTGBM
        self.model: Any = None
        self.medians: pd.Series | None = None

    def fit(self, X: pd.DataFrame, y: np.ndarray, w: np.ndarray | None = None) -> GBMModel:
        # Columns with no data at all break histogram binning; they carry no signal anyway.
        self.features = [c for c in X.columns if X[c].notna().any()]
        X = X[self.features]
        self.medians = X.median(numeric_only=True)
        min_leaf = max(5, len(y) // 12)
        if self.use_lightgbm and _lgb is not None:
            self.hyperparameters = {
                "library": "lightgbm",
                "n_estimators": 150,
                "learning_rate": 0.05,
                "num_leaves": 7,
                "min_child_samples": min_leaf,
                "subsample": 0.8,
                "colsample_bytree": 0.7,
            }
            params = {k: v for k, v in self.hyperparameters.items() if k != "library"}
            self.model = _lgb.LGBMRegressor(
                **params,
                subsample_freq=1,
                reg_lambda=1.0,
                random_state=0,
                verbose=-1,
                n_jobs=1,
            )
        else:
            self.hyperparameters = {
                "library": "sklearn",
                "max_iter": 150,
                "learning_rate": 0.05,
                "max_leaf_nodes": 7,
                "min_samples_leaf": min_leaf,
            }
            params = {k: v for k, v in self.hyperparameters.items() if k != "library"}
            self.model = HistGradientBoostingRegressor(
                **params, l2_regularization=1.0, random_state=0
            )
        self.model.fit(X, y, sample_weight=w)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model.predict(X[self.features]), dtype=float)

    def explain(self, x: pd.DataFrame) -> list[Factor]:
        xf = x[self.features]
        if self.use_lightgbm and _lgb is not None:
            try:
                contrib = self.model.predict(xf, pred_contrib=True)[0][:-1]
                return _top_factors(dict(zip(self.features, map(float, contrib), strict=True)))
            except Exception:  # pragma: no cover - fall through to perturbation
                logger.debug("lightgbm pred_contrib failed, using perturbation")
        # Fallback: effect of resetting each feature to its training median.
        base = float(self.predict(xf)[0])
        assert self.medians is not None
        contribs: dict[str, float] = {}
        for f in self.features:
            v = xf.iloc[0][f]
            med = self.medians.get(f, np.nan)
            if pd.isna(v) or pd.isna(med) or v == med:
                continue
            xm = xf.copy()
            xm.loc[xm.index[0], f] = med
            contribs[f] = base - float(self.predict(xm)[0])
        return _top_factors(contribs)


def make_model(model_type: str, target: str, use_lightgbm: bool = True) -> ForecastModel:
    if model_type == "naive":
        return NaiveModel(target)
    if model_type == "baseline":
        return BaselineModel(target)
    if model_type == "ridge":
        return RidgeModel(target)
    if model_type == "gbm":
        return GBMModel(target, use_lightgbm=use_lightgbm)
    raise ValueError(f"unknown model type {model_type}")
