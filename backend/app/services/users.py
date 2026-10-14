"""User accounts: signup, login, profile, export and hard deletion."""

from __future__ import annotations

import csv
import io
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.models import (
    CustomMetric,
    CustomMetricValue,
    DailyCheckIn,
    ModelVersion,
    Prediction,
    User,
)
from app.ml.schema import CORE_FEELINGS, OPTIONAL_NUMERIC
from app.schemas.auth import SignupIn, UserPatch


class EmailTakenError(Exception):
    pass


def user_artifact_dir(user_id: int) -> Path:
    return Path(get_settings().model_artifact_dir) / f"user_{user_id}"


async def create_user(session: AsyncSession, data: SignupIn) -> User:
    email = data.email.lower()
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailTakenError
    user = User(
        email=email,
        password_hash=hash_password(data.password),
        display_name=data.display_name.strip(),
        timezone=data.timezone,
        onboarding_completed=False,
        token_version=0,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(user.password_hash, password):
        return None
    return user


async def update_user(session: AsyncSession, user: User, patch: UserPatch) -> User:
    data = patch.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"] is not None:
        user.display_name = data["display_name"].strip()
    if "timezone" in data and data["timezone"] is not None:
        user.timezone = data["timezone"]
    if data.get("onboarding_completed"):
        user.onboarding_completed = True
    await session.commit()
    await session.refresh(user)
    return user


def _row(obj: Any, fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        v = getattr(obj, f)
        out[f] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


CHECKIN_FIELDS = [
    "date",
    *CORE_FEELINGS,
    *OPTIONAL_NUMERIC,
    "tags",
    "notes",
    "created_at",
    "updated_at",
]


async def export_user(session: AsyncSession, user: User) -> dict[str, Any]:
    checkins = (
        await session.scalars(
            select(DailyCheckIn).where(DailyCheckIn.user_id == user.id).order_by(DailyCheckIn.date)
        )
    ).all()
    metrics = (
        await session.scalars(select(CustomMetric).where(CustomMetric.user_id == user.id))
    ).all()
    values = (
        await session.scalars(
            select(CustomMetricValue)
            .join(DailyCheckIn, CustomMetricValue.checkin_id == DailyCheckIn.id)
            .where(DailyCheckIn.user_id == user.id)
        )
    ).all()
    by_checkin: dict[int, list[dict[str, Any]]] = {}
    for v in values:
        by_checkin.setdefault(v.checkin_id, []).append({"metric_id": v.metric_id, "value": v.value})
    preds = (
        await session.scalars(
            select(Prediction).where(Prediction.user_id == user.id).order_by(Prediction.target_date)
        )
    ).all()
    mvs = (
        await session.scalars(
            select(ModelVersion).where(ModelVersion.user_id == user.id).order_by(ModelVersion.id)
        )
    ).all()
    pred_fields = [c.name for c in Prediction.__table__.columns if c.name not in ("user_id",)]
    mv_fields = [
        c.name for c in ModelVersion.__table__.columns if c.name not in ("user_id", "artifact_path")
    ]
    return {
        "exported_at": datetime.now(UTC),
        "user": _row(
            user, ["id", "email", "display_name", "timezone", "onboarding_completed", "created_at"]
        ),
        "checkins": [
            {**_row(c, CHECKIN_FIELDS), "custom_metrics": by_checkin.get(c.id, [])}
            for c in checkins
        ],
        "custom_metrics": [_row(m, ["id", "name", "min", "max", "unit"]) for m in metrics],
        "predictions": [_row(p, pred_fields) for p in preds],
        "model_versions": [_row(m, mv_fields) for m in mvs],
    }


async def export_checkins_csv(session: AsyncSession, user: User) -> str:
    checkins = (
        await session.scalars(
            select(DailyCheckIn).where(DailyCheckIn.user_id == user.id).order_by(DailyCheckIn.date)
        )
    ).all()
    buf = io.StringIO()
    fields = [f for f in CHECKIN_FIELDS if f not in ("created_at", "updated_at")]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for c in checkins:
        row = _row(c, fields)
        row["tags"] = ";".join(c.tags or [])
        writer.writerow(row)
    return buf.getvalue()


async def delete_user(session: AsyncSession, user: User) -> None:
    """Hard delete: rows in every table plus model artifacts on disk."""
    uid = user.id
    checkin_ids = select(DailyCheckIn.id).where(DailyCheckIn.user_id == uid)
    await session.execute(
        delete(CustomMetricValue).where(CustomMetricValue.checkin_id.in_(checkin_ids))
    )
    await session.execute(delete(Prediction).where(Prediction.user_id == uid))
    await session.execute(delete(ModelVersion).where(ModelVersion.user_id == uid))
    await session.execute(delete(DailyCheckIn).where(DailyCheckIn.user_id == uid))
    await session.execute(delete(CustomMetric).where(CustomMetric.user_id == uid))
    await session.execute(delete(User).where(User.id == uid))
    await session.commit()
    shutil.rmtree(user_artifact_dir(uid), ignore_errors=True)
