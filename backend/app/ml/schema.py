"""Field lists shared by the ML pipeline. Kept independent of the ORM."""

from __future__ import annotations

CORE_FEELINGS: tuple[str, ...] = ("mood", "energy", "stress", "anxiety", "focus")
TARGETS: tuple[str, ...] = ("mood", "energy", "stress")

OPTIONAL_NUMERIC: tuple[str, ...] = (
    "sleep_hours",
    "sleep_quality",
    "exercise_minutes",
    "outdoor_minutes",
    "screen_time_hours",
    "caffeine_servings",
    "alcohol_units",
    "meals_eaten",
    "social_interaction",
    "workload",
)

ROLLING_FIELDS: tuple[str, ...] = (
    *CORE_FEELINGS,
    "sleep_hours",
    "exercise_minutes",
    "screen_time_hours",
    "workload",
)

VALUE_MIN = 1.0
VALUE_MAX = 10.0

STAGE_NAMES = {0: "collecting", 1: "baseline", 2: "personal_linear", 3: "personal_adaptive"}


def stage_for_days(days_logged: int) -> int:
    """Model stage from the number of distinct logged days."""
    if days_logged < 7:
        return 0
    if days_logged < 21:
        return 1
    if days_logged < 60:
        return 2
    return 3


def days_needed_for_next_stage(days_logged: int) -> int | None:
    for threshold in (7, 21, 60):
        if days_logged < threshold:
            return threshold - days_logged
    return None
