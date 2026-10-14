"""Database models.

Notes:
- ``DailyCheckIn.date`` is the user's *local* calendar date (see ``User.timezone``).
- A ``ModelVersion`` row is one trained model for one target (mood, energy or stress).
  Stage 3 picks the best model per target, so per-target rows keep that simple.
- Model artifacts live on disk (``artifact_path``), never in the database.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.db.base import Base

TARGETS: tuple[str, ...] = ("mood", "energy", "stress")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(64))
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    checkins: Mapped[list[DailyCheckIn]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    metrics: Mapped[list[CustomMetric]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    model_versions: Mapped[list[ModelVersion]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class DailyCheckIn(Base):
    __tablename__ = "daily_checkins"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_checkin_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    mood: Mapped[int] = mapped_column(Integer)
    energy: Mapped[int] = mapped_column(Integer)
    stress: Mapped[int] = mapped_column(Integer)
    anxiety: Mapped[int] = mapped_column(Integer)
    focus: Mapped[int] = mapped_column(Integer)

    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exercise_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outdoor_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    screen_time_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    caffeine_servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alcohol_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meals_eaten: Mapped[int | None] = mapped_column(Integer, nullable=True)
    social_interaction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workload: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Python-side timestamps (microsecond precision on every backend).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="checkins")
    metric_values: Mapped[list[CustomMetricValue]] = relationship(
        back_populates="checkin", cascade="all, delete-orphan", passive_deletes=True
    )


class CustomMetric(Base):
    __tablename__ = "custom_metrics"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_metric_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    min: Mapped[float] = mapped_column(Float)
    max: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    user: Mapped[User] = relationship(back_populates="metrics")
    values: Mapped[list[CustomMetricValue]] = relationship(
        back_populates="metric", cascade="all, delete-orphan", passive_deletes=True
    )


class CustomMetricValue(Base):
    __tablename__ = "custom_metric_values"
    __table_args__ = (UniqueConstraint("checkin_id", "metric_id", name="uq_metric_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    checkin_id: Mapped[int] = mapped_column(
        ForeignKey("daily_checkins.id", ondelete="CASCADE"), index=True
    )
    metric_id: Mapped[int] = mapped_column(
        ForeignKey("custom_metrics.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[float] = mapped_column(Float)

    checkin: Mapped[DailyCheckIn] = relationship(back_populates="metric_values")
    metric: Mapped[CustomMetric] = relationship(back_populates="values")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target: Mapped[str] = mapped_column(String(16))
    model_type: Mapped[str] = mapped_column(String(16))  # naive | baseline | ridge | gbm
    stage: Mapped[int] = mapped_column(Integer)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trained_through: Mapped[date] = mapped_column(Date)
    # Latest check-in change included in this training (decides if a retrain is needed).
    data_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    n_training_days: Mapped[int] = mapped_column(Integer)
    feature_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    hyperparameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    backtest_mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    naive_mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    backtest_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    interval_halfwidth: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped[User] = relationship(back_populates="model_versions")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "target_date", name="uq_prediction_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    stage: Mapped[int] = mapped_column(Integer)
    days_since_last_log: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mood_model_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )
    energy_model_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )
    stress_model_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )

    mood_predicted: Mapped[float] = mapped_column(Float)
    mood_lower: Mapped[float] = mapped_column(Float)
    mood_upper: Mapped[float] = mapped_column(Float)
    mood_naive: Mapped[float | None] = mapped_column(Float, nullable=True)
    mood_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    mood_abs_error: Mapped[float | None] = mapped_column(Float, nullable=True)

    energy_predicted: Mapped[float] = mapped_column(Float)
    energy_lower: Mapped[float] = mapped_column(Float)
    energy_upper: Mapped[float] = mapped_column(Float)
    energy_naive: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy_abs_error: Mapped[float | None] = mapped_column(Float, nullable=True)

    stress_predicted: Mapped[float] = mapped_column(Float)
    stress_lower: Mapped[float] = mapped_column(Float)
    stress_upper: Mapped[float] = mapped_column(Float)
    stress_naive: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_abs_error: Mapped[float | None] = mapped_column(Float, nullable=True)

    # {"mood": "ridge", ...}: model type actually used for each target.
    model_types: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    # {"mood": [{"feature", "label", "note", "direction", "contribution"}], ...}
    top_factors: Mapped[dict[str, list[dict[str, Any]]]] = mapped_column(JSON, default=dict)

    user: Mapped[User] = relationship(back_populates="predictions")
