"""Simple, honest, data-backed insights.

Insights are phrased as observations, never causes, and always show the sample size.
They use only structured fields: the free-text ``notes`` field is never analysed.
"""

from __future__ import annotations

import math
from typing import Literal

import pandas as pd
from scipy import stats

from app.ml.schema import OPTIONAL_NUMERIC
from app.schemas.misc import InsightOut

MIN_CORRELATION_N = 21
MIN_ABS_R = 0.3
MIN_WEEKDAY_SAMPLES = 3
MIN_TAG_OCCURRENCES = 5
MIN_TAG_DIFF = 0.3

FACTOR_TEXT: dict[str, tuple[str, str, str]] = {
    # field: (comparative phrase, unit, gentle note)
    "sleep_hours": ("more sleep", "hours", "your sleep"),
    "sleep_quality": ("better sleep", "out of 5", "how you slept"),
    "exercise_minutes": ("more exercise", "minutes", "moving your body"),
    "outdoor_minutes": ("more time outdoors", "minutes", "time outdoors"),
    "screen_time_hours": ("more screen time", "hours", "screen time"),
    "caffeine_servings": ("more caffeine", "servings", "caffeine"),
    "alcohol_units": ("more alcohol", "units", "alcohol"),
    "meals_eaten": ("more meals", "meals", "regular meals"),
    "social_interaction": ("more time with people", "out of 5", "time with friends"),
    "workload": ("a heavier workload", "out of 5", "a heavy workload"),
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _pairs(daily: pd.DataFrame) -> pd.DataFrame:
    """Rows of day t (logged) joined with next-day mood (t+1 logged)."""
    nxt = daily.shift(-1)
    ok = daily["logged"].astype(bool) & nxt["logged"].astype("boolean").fillna(False).astype(bool)
    out = daily[ok].copy()
    out["next_mood"] = nxt.loc[ok, "mood"].astype(float)
    return out


def _fmt(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".") if abs(x - round(x)) > 1e-9 else str(round(x))


def correlation_insights(
    daily: pd.DataFrame, custom_names: dict[str, str] | None = None
) -> list[InsightOut]:
    pairs = _pairs(daily)
    out: list[InsightOut] = []
    factors: list[tuple[str, str, str, str]] = [
        (f, *FACTOR_TEXT[f]) for f in OPTIONAL_NUMERIC if f in pairs.columns
    ]
    for col, name in (custom_names or {}).items():
        if col in pairs.columns:
            factors.append((col, f"more {name.lower()}", "", name.lower()))
    for col, noun, unit, note in factors:
        sub = pairs[[col, "next_mood"]].dropna()
        n = len(sub)
        if n < MIN_CORRELATION_N or sub[col].nunique() < 3:
            continue
        r = float(stats.spearmanr(sub[col], sub["next_mood"]).statistic)
        if math.isnan(r) or abs(r) < MIN_ABS_R:
            continue
        median = float(sub[col].median())
        high = sub[sub[col] > median]["next_mood"]
        low = sub[sub[col] <= median]["next_mood"]
        if len(high) < 3 or len(low) < 3:
            continue
        diff = float(high.mean() - low.mean())
        direction = "higher" if diff > 0 else "lower"
        unit_txt = f" {unit}" if unit else ""
        text = (
            f"On days after {noun} than your usual (above {_fmt(median)}{unit_txt}), "
            f"your next-day mood has averaged {abs(diff):.1f} points {direction} "
            f"(n = {len(high)} vs {len(low)} days)."
        )
        out.append(
            InsightOut(
                kind="correlation",
                factor=col,
                text=text,
                note=note,
                direction=direction,
                n=n,
                effect=round(diff, 2),
                r=round(r, 2),
            )
        )
    out.sort(key=lambda i: abs(i.r or 0), reverse=True)
    return out


def weekday_insights(daily: pd.DataFrame) -> list[InsightOut]:
    logged = daily[daily["logged"].astype(bool)]
    if logged.empty:
        return []
    by_dow = logged.groupby(pd.DatetimeIndex(logged.index).dayofweek)["mood"]
    counts = by_dow.count()
    if len(counts) < 7 or int(counts.min()) < MIN_WEEKDAY_SAMPLES:
        return []
    means = by_dow.mean()
    overall = float(logged["mood"].mean())
    best, worst = int(means.to_numpy().argmax()), int(means.to_numpy().argmin())
    best, worst = int(means.index[best]), int(means.index[worst])
    if best == worst:
        return []
    items = []
    pairs: tuple[tuple[int, Literal["higher", "lower"]], ...] = (
        (best, "higher"),
        (worst, "lower"),
    )
    for dow, direction in pairs:
        word = "brightest" if direction == "higher" else "heaviest"
        diff = float(means[dow] - overall)
        items.append(
            InsightOut(
                kind="weekday",
                factor=WEEKDAYS[dow].lower(),
                text=(
                    f"{WEEKDAYS[dow]}s tend to be your {word} days: mood averages "
                    f"{means[dow]:.1f} compared with {overall:.1f} overall "
                    f"(n = {int(counts[dow])} {WEEKDAYS[dow]}s)."
                ),
                note=f"{WEEKDAYS[dow].lower()}s",
                direction=direction,
                n=int(counts[dow]),
                effect=round(diff, 2),
            )
        )
    return items


def tag_insights(daily: pd.DataFrame) -> list[InsightOut]:
    pairs = _pairs(daily)
    if pairs.empty:
        return []
    all_tags = sorted({t for tags in pairs["tags"] for t in tags})
    out: list[InsightOut] = []
    for tag in all_tags:
        has = pairs["tags"].apply(lambda ts, tag=tag: tag in ts)
        n_with, n_without = int(has.sum()), int((~has).sum())
        if n_with < MIN_TAG_OCCURRENCES or n_without < MIN_TAG_OCCURRENCES:
            continue
        diff = float(pairs.loc[has, "next_mood"].mean() - pairs.loc[~has, "next_mood"].mean())
        if abs(diff) < MIN_TAG_DIFF:
            continue
        direction: Literal["higher", "lower"] = "higher" if diff > 0 else "lower"
        out.append(
            InsightOut(
                kind="tag",
                factor=tag,
                text=(
                    f"The day after a day tagged '{tag}', your mood has averaged "
                    f"{abs(diff):.1f} points {direction} than after other days "
                    f"(n = {n_with} vs {n_without} days)."
                ),
                note=tag,
                direction=direction,
                n=n_with,
                effect=round(diff, 2),
            )
        )
    out.sort(key=lambda i: abs(i.effect), reverse=True)
    return out


def compute_insights(
    daily: pd.DataFrame, custom_names: dict[str, str] | None = None
) -> list[InsightOut]:
    if daily.empty:
        return []
    return [
        *correlation_insights(daily, custom_names),
        *weekday_insights(daily),
        *tag_insights(daily),
    ]
