"""Twin status and accuracy tracking ("your twin is getting smarter")."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelVersion, Prediction, User
from app.ml.schema import STAGE_NAMES, TARGETS, days_needed_for_next_stage, stage_for_days
from app.schemas.misc import AccuracyPointOut, TargetAccuracyOut, TargetModelOut, TwinOut
from app.services.checkins import count_logged_days
from app.services.twin import active_versions


def _mean(xs: list[float]) -> float | None:
    return round(float(np.mean(xs)), 3) if xs else None


def target_accuracy(preds: list[Prediction], target: str, today: date) -> TargetAccuracyOut:
    scored = [p for p in preds if getattr(p, f"{target}_abs_error") is not None]
    last7 = [p for p in scored if p.target_date > today - timedelta(days=7)]
    last30 = [p for p in scored if p.target_date > today - timedelta(days=30)]
    err7 = [getattr(p, f"{target}_abs_error") for p in last7]
    err30 = [getattr(p, f"{target}_abs_error") for p in last30]
    naive30 = [
        abs(getattr(p, f"{target}_naive") - getattr(p, f"{target}_actual"))
        for p in last30
        if getattr(p, f"{target}_naive") is not None
    ]
    within = [e <= 1.0 for e in err30]
    covered = [
        getattr(p, f"{target}_lower")
        <= getattr(p, f"{target}_actual")
        <= getattr(p, f"{target}_upper")
        for p in last30
    ]
    mae30 = _mean(err30)
    naive_mae30 = _mean(naive30)
    improvement = None
    if mae30 is not None and naive_mae30:
        improvement = round(100.0 * (1.0 - mae30 / naive_mae30), 1)
    return TargetAccuracyOut(
        mae_7d=_mean(err7),
        mae_30d=mae30,
        naive_mae_30d=naive_mae30,
        within_1_rate=_mean([float(w) for w in within]),
        improvement_vs_naive_pct=improvement,
        interval_coverage=_mean([float(c) for c in covered]),
        n_scored=len(scored),
    )


def accuracy_series(preds: list[Prediction], window: int = 7) -> list[AccuracyPointOut]:
    scored = sorted((p for p in preds if p.mood_abs_error is not None), key=lambda p: p.target_date)
    out: list[AccuracyPointOut] = []
    for i, p in enumerate(scored):
        win = scored[max(0, i - window + 1) : i + 1]
        errs = [getattr(q, f"{t}_abs_error") for q in win for t in TARGETS]
        naive = [
            abs(getattr(q, f"{t}_naive") - getattr(q, f"{t}_actual"))
            for q in win
            for t in TARGETS
            if getattr(q, f"{t}_naive") is not None
        ]
        out.append(
            AccuracyPointOut(
                date=p.target_date,
                mood_abs_error=p.mood_abs_error,
                energy_abs_error=p.energy_abs_error,
                stress_abs_error=p.stress_abs_error,
                mae_7d=_mean(errs),
                naive_mae_7d=_mean(naive),
            )
        )
    return out


async def twin_status(session: AsyncSession, user: User, today: date) -> TwinOut:
    n = await count_logged_days(session, user)
    stage = stage_for_days(n)
    active = await active_versions(session, user)
    preds = list(
        (
            await session.scalars(
                select(Prediction)
                .where(Prediction.user_id == user.id)
                .order_by(Prediction.target_date)
            )
        ).all()
    )
    last_trained = await session.scalar(
        select(ModelVersion.trained_at)
        .where(ModelVersion.user_id == user.id)
        .order_by(ModelVersion.trained_at.desc())
        .limit(1)
    )
    accuracy = {t: target_accuracy(preds, t, today) for t in TARGETS}
    rates = [a.within_1_rate for a in accuracy.values() if a.within_1_rate is not None]
    models = {
        t: TargetModelOut(
            model_type=active[t].model_type if t in active else None,
            trained_at=active[t].trained_at if t in active else None,
            backtest_mae=active[t].backtest_mae if t in active else None,
            naive_mae=active[t].naive_mae if t in active else None,
            backtest_coverage=active[t].backtest_coverage if t in active else None,
        )
        for t in TARGETS
    }
    return TwinOut(
        stage=stage,
        stage_name=STAGE_NAMES[stage],
        days_logged=n,
        days_to_next_stage=days_needed_for_next_stage(n),
        last_trained_at=last_trained,
        in_tune_pct=round(100.0 * float(np.mean(rates)), 0) if rates else None,
        models=models,
        accuracy=accuracy,
        series=accuracy_series(preds),
    )
