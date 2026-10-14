"""Staged training, model selection and the promotion rule.

Promotion rule (spec 4.2): a challenger becomes active only if its backtest MAE beats
both naive persistence and the active model on the same backtest days.

"Beats" means: lower MAE by at least ``min_improvement`` (default 2%) on at least 5
backtest days. For fitted models (ridge, gbm) it also means a one-sided paired t-test
on the daily absolute errors with p < ``promotion_p_value`` (default 0.05), so a lucky
stretch of days cannot promote an overfit model for a user with no real signal.

The challenger is chosen by walking up in complexity (naive -> baseline -> ridge -> gbm):
each step must beat the simpler choice so far. If nothing beats naive persistence, the
active model is ``naive`` itself: we never ship a model worse than "tomorrow = today".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from app.ml.data import days_logged
from app.ml.evaluation import (
    BacktestResult,
    backtest_window,
    conformal_halfwidth,
    rolling_origin_backtest,
    sequential_coverage,
)
from app.ml.features import (
    FeatureSpec,
    build_features,
    fit_feature_spec,
    make_targets,
    training_rows,
)
from app.ml.models import ForecastModel, RidgeModel, make_model, recency_weights
from app.ml.schema import TARGETS, stage_for_days

STAGE_CANDIDATES: dict[int, tuple[str, ...]] = {
    1: ("baseline",),
    2: ("baseline", "ridge"),
    3: ("baseline", "ridge", "gbm"),
}
MIN_EVIDENCE_DAYS = 5
# Simpler models are preferred; a more complex one must clearly beat the simpler choice.
COMPLEXITY_ORDER: tuple[str, ...] = ("baseline", "ridge", "gbm")


@dataclass
class TrainConfig:
    recency_half_life_days: float = 60.0
    baseline_half_life_days: float = 3.0
    backtest_max_days: int = 30
    backtest_fraction: float = 0.25
    coverage: float = 0.8
    min_improvement: float = 0.02
    promotion_p_value: float = 0.05
    gap_revert_days: int = 3
    use_lightgbm: bool = True


@dataclass
class CandidateResult:
    target: str
    model_type: str
    backtest: BacktestResult
    halfwidth: float
    coverage: float | None
    model: ForecastModel | None = None  # fitted on all rows once chosen
    n_training_days: int = 0

    @property
    def mae(self) -> float:
        return self.backtest.mae


@dataclass
class TargetDecision:
    target: str
    naive_mae: float
    candidates: dict[str, CandidateResult]
    winner: CandidateResult
    previous_type: str | None
    reason: str


@dataclass
class TrainingOutcome:
    stage: int
    days_logged: int
    spec: FeatureSpec
    feature_list: list[str]
    decisions: dict[str, TargetDecision] = field(default_factory=dict)


def _beats(a_err: np.ndarray, b_err: np.ndarray, margin: float, p_value: float | None) -> bool:
    """True if errors ``a`` are lower than ``b`` by the margin (and, if ``p_value`` is
    given, by more than chance: one-sided paired t-test on daily absolute errors).

    Needs at least ``MIN_EVIDENCE_DAYS`` paired backtest days either way.
    """
    if len(a_err) < MIN_EVIDENCE_DAYS:
        return False
    ma, mb = float(np.mean(a_err)), float(np.mean(b_err))
    if not ma < mb * (1.0 - margin):
        return False
    if p_value is None:
        return True
    diff = np.asarray(a_err) - np.asarray(b_err)
    if np.allclose(diff, diff[0]):
        return True
    p = float(stats.ttest_rel(a_err, b_err, alternative="less").pvalue)
    return bool(np.isnan(p) or p < p_value)


def prepare(
    daily: pd.DataFrame, cfg: TrainConfig, spec: FeatureSpec | None = None
) -> tuple[FeatureSpec, pd.DataFrame, pd.DataFrame, pd.Index]:
    spec = spec or fit_feature_spec(daily, cfg.baseline_half_life_days)
    X = build_features(daily, spec)
    Y = make_targets(daily)
    rows = training_rows(X, Y, cfg.gap_revert_days)
    return spec, X, Y, rows


def evaluate_candidate(
    model_type: str,
    target: str,
    X: pd.DataFrame,
    y: pd.Series,
    cfg: TrainConfig,
    n_test: int,
) -> CandidateResult:
    fixed_alpha: float | None = None
    if model_type == "ridge":
        # Choose alpha once, on data before the backtest window (no peeking), then
        # reuse it in every fold. Much faster than a nested search per fold.
        start = max(0, len(X) - n_test)
        ytr = y.iloc[:start].to_numpy(dtype=float)
        fixed_alpha = RidgeModel(target).choose_alpha(
            X.iloc[:start], ytr, recency_weights(X.index[:start], cfg.recency_half_life_days)
        )

    def factory() -> ForecastModel:
        if model_type == "ridge":
            return RidgeModel(target, fixed_alpha=fixed_alpha)
        return make_model(model_type, target, cfg.use_lightgbm)

    bt = rolling_origin_backtest(factory, X, y, n_test, cfg.recency_half_life_days)
    return CandidateResult(
        target=target,
        model_type=model_type,
        backtest=bt,
        halfwidth=conformal_halfwidth(bt.residuals, cfg.coverage),
        coverage=sequential_coverage(bt.residuals, cfg.coverage),
    )


def fit_final(c: CandidateResult, X: pd.DataFrame, y: pd.Series, cfg: TrainConfig) -> None:
    m = make_model(c.model_type, c.target, cfg.use_lightgbm)
    if m.needs_fit:
        m.fit(X, y.to_numpy(dtype=float), recency_weights(X.index, cfg.recency_half_life_days))
    else:
        m.features = list(X.columns)
    c.model = m
    c.n_training_days = len(X)


def train_user(
    daily: pd.DataFrame,
    active_types: dict[str, str | None] | None = None,
    cfg: TrainConfig | None = None,
) -> TrainingOutcome:
    """Train, backtest and select models for every target."""
    cfg = cfg or TrainConfig()
    active_types = active_types or {}
    n_logged = days_logged(daily)
    stage = stage_for_days(n_logged)
    spec, X_all, Y_all, rows = prepare(daily, cfg)
    outcome = TrainingOutcome(
        stage=stage, days_logged=n_logged, spec=spec, feature_list=list(X_all.columns)
    )
    if stage == 0 or len(rows) == 0:
        return outcome

    X = X_all.loc[rows]
    candidates = STAGE_CANDIDATES[stage]

    for target in TARGETS:
        y = Y_all.loc[rows, target]
        incumbent = active_types.get(target)
        types = list(dict.fromkeys([*candidates, *([incumbent] if incumbent else [])]))
        types = [t for t in types if t != "naive"]
        fitted = any(make_model(t, target).needs_fit for t in types)
        n_test = backtest_window(len(X), cfg.backtest_max_days, cfg.backtest_fraction, fitted)

        results = {t: evaluate_candidate(t, target, X, y, cfg, n_test) for t in types}
        naive = evaluate_candidate("naive", target, X, y, cfg, n_test)
        naive_mae = naive.mae

        def errs(r: CandidateResult) -> np.ndarray:
            return np.abs(r.backtest.residuals)

        m = cfg.min_improvement

        def pv(model: CandidateResult) -> float | None:
            # Fitted models (ridge, gbm) can overfit, so they must also pass a
            # significance test. The baseline has nothing to fit: a plain MAE win will do.
            return cfg.promotion_p_value if model.model_type in ("ridge", "gbm") else None

        # 1. Challenger: walk up in complexity. A model qualifies only if it clearly
        #    beats the best (lowest-MAE) of naive persistence and every simpler model.
        challenger = naive
        simpler: list[CandidateResult] = [naive]
        for t in COMPLEXITY_ORDER:
            if t not in results:
                continue
            ref = min(simpler, key=lambda r: r.mae)
            if t in candidates and _beats(errs(results[t]), errs(ref), m, pv(results[t])):
                challenger = results[t]
            simpler.append(results[t])

        # 2. Promotion rule against the active model.
        inc = results.get(incumbent) if incumbent not in (None, "naive") else None
        if incumbent == "naive":
            inc = naive
        if inc is None:
            winner = challenger
            reason = (
                "promoted: first model, beats naive persistence"
                if challenger is not naive
                else "fallback: nothing beat naive persistence yet"
            )
        elif challenger.model_type == inc.model_type:
            winner, reason = inc, "refreshed: active model retrained on new data"
        elif challenger is not naive and _beats(errs(challenger), errs(inc), m, pv(challenger)):
            winner, reason = challenger, "promoted: beats naive persistence and the active model"
        elif inc is not naive and inc.mae < naive_mae:
            winner, reason = inc, "kept: no challenger clearly beat the active model"
        else:
            winner, reason = challenger, "replaced: active model fell behind naive persistence"

        fit_final(winner, X, y, cfg)
        outcome.decisions[target] = TargetDecision(
            target=target,
            naive_mae=naive_mae,
            candidates={**results, "naive": naive},
            winner=winner,
            previous_type=incumbent,
            reason=reason,
        )
    return outcome


def artifact_payload(outcome: TrainingOutcome, target: str) -> dict[str, Any]:
    d = outcome.decisions[target]
    return {
        "target": target,
        "model_type": d.winner.model_type,
        "model": d.winner.model,
        "spec": outcome.spec,
        "halfwidth": d.winner.halfwidth,
        "feature_list": outcome.feature_list,
    }


def mae_or_none(v: float) -> float | None:
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 4)
