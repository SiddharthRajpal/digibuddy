"""Orchestrates the prediction engine for a user: training, forecasting and scoring.

The ML code in ``app.ml`` knows nothing about the database; this module loads data,
calls it, and persists ``ModelVersion`` and ``Prediction`` rows.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models import CustomMetric, DailyCheckIn, ModelVersion, Prediction, User
from app.ml.data import custom_metric_column, records_to_daily
from app.ml.predict import Forecast, forecast_next_day
from app.ml.schema import TARGETS, stage_for_days
from app.ml.training import TrainConfig, TrainingOutcome, artifact_payload, mae_or_none, train_user
from app.schemas.predictions import FactorOut, ForecastOut, TargetForecastOut
from app.services.checkins import count_logged_days, to_record
from app.services.users import user_artifact_dir

logger = logging.getLogger(__name__)


def train_config() -> TrainConfig:
    s = get_settings()
    return TrainConfig(
        recency_half_life_days=s.recency_half_life_days,
        baseline_half_life_days=s.baseline_half_life_days,
        backtest_max_days=s.backtest_max_days,
        backtest_fraction=s.backtest_fraction,
        coverage=s.interval_coverage,
        min_improvement=s.promotion_min_improvement,
        gap_revert_days=s.gap_revert_days,
        use_lightgbm=s.use_lightgbm,
    )


async def custom_metric_names(session: AsyncSession, user: User) -> dict[str, str]:
    metrics = (
        await session.scalars(select(CustomMetric).where(CustomMetric.user_id == user.id))
    ).all()
    return {custom_metric_column(m.id): m.name for m in metrics}


async def load_daily(session: AsyncSession, user: User, through: date | None = None) -> Any:
    q = (
        select(DailyCheckIn)
        .options(selectinload(DailyCheckIn.metric_values))
        .where(DailyCheckIn.user_id == user.id)
    )
    if through is not None:
        q = q.where(DailyCheckIn.date <= through)
    rows = (await session.scalars(q.order_by(DailyCheckIn.date))).all()
    return records_to_daily([to_record(c) for c in rows], through=through)


async def active_versions(session: AsyncSession, user: User) -> dict[str, ModelVersion]:
    rows = (
        await session.scalars(
            select(ModelVersion).where(ModelVersion.user_id == user.id, ModelVersion.is_active)
        )
    ).all()
    return {mv.target: mv for mv in rows}


def load_artifact(mv: ModelVersion | None) -> dict[str, Any] | None:
    if mv is None or not mv.artifact_path:
        return None
    try:
        data: dict[str, Any] = joblib.load(mv.artifact_path)
        return data
    except Exception:
        logger.warning("could not load model artifact model_version_id=%s", mv.id)
        return None


async def retrain(
    session: AsyncSession, user: User, as_of: date, now: datetime
) -> TrainingOutcome | None:
    """Train on data through ``as_of``, backtest, and promote per the rule in 4.2."""
    started = time.perf_counter()
    daily = await load_daily(session, user, through=as_of)
    if daily.empty:
        return None
    data_updated_at = await _latest_checkin_change(session, user)
    active = await active_versions(session, user)
    active_types: dict[str, str | None] = {t: mv.model_type for t, mv in active.items()}
    cfg = train_config()
    outcome = await asyncio.to_thread(train_user, daily, active_types, cfg)
    if not outcome.decisions:
        return outcome

    art_dir = user_artifact_dir(user.id)
    art_dir.mkdir(parents=True, exist_ok=True)
    for target, decision in outcome.decisions.items():
        winner = decision.winner
        await session.execute(
            update(ModelVersion)
            .where(
                ModelVersion.user_id == user.id,
                ModelVersion.target == target,
                ModelVersion.is_active,
            )
            .values(is_active=False)
        )
        for mtype, cand in decision.candidates.items():
            is_winner = cand is winner
            mv = ModelVersion(
                user_id=user.id,
                target=target,
                model_type=mtype,
                stage=outcome.stage,
                trained_at=now,
                trained_through=as_of,
                data_updated_at=data_updated_at,
                n_training_days=winner.n_training_days,
                feature_list=outcome.feature_list if mtype in ("ridge", "gbm") else [],
                hyperparameters=(cand.model.hyperparameters if is_winner and cand.model else {})
                | {"selection": decision.reason if is_winner else "candidate"},
                backtest_mae=mae_or_none(cand.mae),
                naive_mae=mae_or_none(decision.naive_mae),
                backtest_coverage=cand.coverage,
                interval_halfwidth=round(cand.halfwidth, 4),
                is_active=is_winner,
            )
            session.add(mv)
            if is_winner:
                await session.flush()
                path = Path(art_dir) / f"mv_{mv.id}.joblib"
                await asyncio.to_thread(joblib.dump, artifact_payload(outcome, target), path)
                mv.artifact_path = str(path)
    await session.commit()
    logger.info(
        "retrain user_id=%s stage=%s ms=%.0f",
        user.id,
        outcome.stage,
        (time.perf_counter() - started) * 1000,
    )
    return outcome


async def _latest_checkin_change(session: AsyncSession, user: User) -> datetime | None:
    return await session.scalar(
        select(func.max(DailyCheckIn.updated_at)).where(DailyCheckIn.user_id == user.id)
    )


async def needs_retrain(session: AsyncSession, user: User) -> bool:
    """True if any check-in changed since the data the last training saw."""
    latest = await _latest_checkin_change(session, user)
    if latest is None:
        return False
    seen = await session.scalar(
        select(func.max(ModelVersion.data_updated_at)).where(ModelVersion.user_id == user.id)
    )
    return seen is None or latest > seen


async def get_prediction(session: AsyncSession, user: User, target_date: date) -> Prediction | None:
    return await session.scalar(
        select(Prediction).where(
            Prediction.user_id == user.id, Prediction.target_date == target_date
        )
    )


async def generate_prediction(
    session: AsyncSession, user: User, origin: date, now: datetime
) -> Prediction | None:
    """Forecast ``origin + 1`` from data through ``origin`` with the active models.

    No retraining happens here, except a one-off first training when a user has just
    reached 7 logged days and no model exists yet. Scored predictions are never
    overwritten, and no forecast is made for a day that is already logged.
    """
    target_date = origin + timedelta(days=1)
    n = await count_logged_days(session, user, through=origin)
    stage = stage_for_days(n)
    if stage == 0:
        return None
    existing = await get_prediction(session, user, target_date)
    if existing is not None and existing.mood_actual is not None:
        return existing
    already_logged = await session.scalar(
        select(DailyCheckIn.id).where(
            DailyCheckIn.user_id == user.id, DailyCheckIn.date == target_date
        )
    )
    if already_logged is not None:
        return existing

    active = await active_versions(session, user)
    if not active:
        await retrain(session, user, origin, now)
        active = await active_versions(session, user)

    daily = await load_daily(session, user, through=origin)
    artifacts = {t: load_artifact(active.get(t)) for t in TARGETS}
    names = await custom_metric_names(session, user)
    s = get_settings()
    fc: Forecast = await asyncio.to_thread(
        forecast_next_day,
        daily,
        origin,
        artifacts,
        s.gap_revert_days,
        names,
        s.baseline_half_life_days,
    )

    p = existing or Prediction(user_id=user.id, target_date=target_date)
    p.stage = stage
    p.days_since_last_log = fc.days_since_last_log
    p.created_at = now
    p.model_types = {t: fc.targets[t].model_type for t in TARGETS}
    p.top_factors = {t: fc.targets[t].factors for t in TARGETS}
    for t in TARGETS:
        tf = fc.targets[t]
        setattr(p, f"{t}_predicted", tf.predicted)
        setattr(p, f"{t}_lower", tf.lower)
        setattr(p, f"{t}_upper", tf.upper)
        setattr(p, f"{t}_naive", tf.naive)
        mv = active.get(t)
        setattr(p, f"{t}_model_version_id", mv.id if mv else None)
    if existing is None:
        session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def score_date(
    session: AsyncSession, user: User, d: date, checkin: DailyCheckIn | None
) -> Prediction | None:
    """Fill (or clear) actuals and errors on the prediction for day ``d``."""
    p = await get_prediction(session, user, d)
    if p is None:
        return None
    for t in TARGETS:
        if checkin is None:
            setattr(p, f"{t}_actual", None)
            setattr(p, f"{t}_abs_error", None)
            continue
        actual = float(getattr(checkin, t))
        setattr(p, f"{t}_actual", actual)
        setattr(p, f"{t}_abs_error", round(abs(getattr(p, f"{t}_predicted") - actual), 2))
    await session.commit()
    await session.refresh(p)
    return p


def prediction_to_out(p: Prediction) -> ForecastOut:
    def target(t: str) -> TargetForecastOut:
        return TargetForecastOut(
            predicted=getattr(p, f"{t}_predicted"),
            lower=getattr(p, f"{t}_lower"),
            upper=getattr(p, f"{t}_upper"),
            actual=getattr(p, f"{t}_actual"),
            abs_error=getattr(p, f"{t}_abs_error"),
            model_type=(p.model_types or {}).get(t),
            factors=[FactorOut(**f) for f in (p.top_factors or {}).get(t, [])],
        )

    return ForecastOut(
        target_date=p.target_date,
        stage=p.stage,
        days_since_last_log=p.days_since_last_log,
        created_at=p.created_at,
        mood=target("mood"),
        energy=target("energy"),
        stress=target("stress"),
    )
