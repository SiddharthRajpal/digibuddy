"""Feature engineering.

Each row of the feature frame is indexed by an *origin* day ``t`` and describes what
was known at the end of day ``t``. The model uses it to predict day ``t + 1``.

No leakage: every feature is built from backward-looking operations only
(positive shifts, trailing rolling windows, expanding statistics). The calendar
features for the target day use only the date, never data. ``tests/test_leakage.py``
checks this by rebuilding features on truncated data.

Column choices that depend on the data (which tags and custom metrics to use) are
fixed in a ``FeatureSpec`` fitted on training data, so the feature columns are stable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.ml.schema import CORE_FEELINGS, OPTIONAL_NUMERIC, ROLLING_FIELDS, TARGETS

TOP_TAGS = 10
MIN_CUSTOM_METRIC_VALUES = 14
LOW_MOOD_THRESHOLD = 4
DOW_SHRINKAGE = 4.0


@dataclass(frozen=True)
class FeatureSpec:
    top_tags: tuple[str, ...] = field(default_factory=tuple)
    custom_metrics: tuple[str, ...] = field(default_factory=tuple)
    baseline_half_life_days: float = 3.0


def fit_feature_spec(daily: pd.DataFrame, baseline_half_life_days: float = 3.0) -> FeatureSpec:
    logged = daily[daily["logged"]] if not daily.empty else daily
    counts: Counter[str] = Counter()
    for tags in logged.get("tags", []):
        counts.update(set(tags))
    top = tuple(sorted(t for t, _ in counts.most_common(TOP_TAGS)))
    cms = tuple(
        c
        for c in daily.columns
        if str(c).startswith("cm_") and int(daily[c].notna().sum()) >= MIN_CUSTOM_METRIC_VALUES
    )
    return FeatureSpec(
        top_tags=top, custom_metrics=cms, baseline_half_life_days=baseline_half_life_days
    )


def _safe_tag(tag: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in tag)


def _streak(flags: pd.Series) -> pd.Series:
    """Length of the run of True values ending at each position."""
    out = np.zeros(len(flags), dtype=float)
    run = 0
    for i, v in enumerate(flags.to_numpy()):
        run = run + 1 if bool(v) else 0
        out[i] = run
    return pd.Series(out, index=flags.index)


def build_features(daily: pd.DataFrame, spec: FeatureSpec) -> pd.DataFrame:
    """Build the feature frame (one row per calendar day of ``daily``)."""
    cal = daily
    idx = pd.DatetimeIndex(cal.index)
    logged = cal[cal["logged"]]
    feats: dict[str, pd.Series] = {}

    # Recency of data.
    last_logged = pd.Series(logged.index, index=logged.index).reindex(idx).ffill()
    feats["days_since_last_log"] = (pd.Series(idx, index=idx) - last_logged).dt.days.astype(float)

    # Lags of core feelings over the sequence of logged days (handles gaps).
    for f in CORE_FEELINGS:
        s = logged[f].astype(float)
        for k in (0, 1, 2):
            feats[f"{f}_lag{k}"] = s.shift(k).reindex(idx).ffill()

    # Rolling means / stds over calendar windows (NaNs are skipped).
    for f in ROLLING_FIELDS:
        col = cal[f].astype(float)
        for w in (3, 7):
            roll = col.rolling(w, min_periods=1)
            feats[f"{f}_mean_{w}d"] = roll.mean()
            feats[f"{f}_std_{w}d"] = col.rolling(w, min_periods=2).std()

    for f in CORE_FEELINGS:
        feats[f"{f}_delta_7d"] = feats[f"{f}_lag0"] - feats[f"{f}_mean_7d"]

    # Sleep debt against the user's personal (expanding, causal) median.
    sleep = cal["sleep_hours"].astype(float)
    personal_median = sleep.expanding(min_periods=1).median().ffill()
    debt = (personal_median - sleep).fillna(0.0)
    feats["sleep_debt_3d"] = debt.rolling(3, min_periods=1).sum()

    # Calendar features of the *target* day (t + 1).
    target_dow = (idx + pd.Timedelta(days=1)).dayofweek.to_numpy()
    feats["target_dow_sin"] = pd.Series(np.sin(2 * np.pi * target_dow / 7), index=idx)
    feats["target_dow_cos"] = pd.Series(np.cos(2 * np.pi * target_dow / 7), index=idx)
    feats["target_is_weekend"] = pd.Series((target_dow >= 5).astype(float), index=idx)

    # Tags.
    tags = cal["tags"]
    for tag in spec.top_tags:
        name = _safe_tag(tag)
        today = pd.Series([1.0 if tag in t else 0.0 for t in tags], index=idx)
        feats[f"tag_{name}"] = today
        feats[f"tag_{name}_3d"] = today.rolling(3, min_periods=1).max()

    # Streaks.
    low = (logged["mood"] <= LOW_MOOD_THRESHOLD).astype(bool)
    feats["low_mood_streak"] = _streak(low).reindex(idx).ffill().fillna(0.0)
    feats["exercise_streak"] = _streak(cal["exercise_minutes"].fillna(0) > 0)

    # Same-day optional values and missing indicators.
    for f in OPTIONAL_NUMERIC:
        feats[f] = cal[f].astype(float)
        feats[f"missing_{f}"] = cal[f].isna().astype(float)

    for c in spec.custom_metrics:
        if c in cal.columns:
            feats[c] = cal[c].astype(float)
        else:
            feats[c] = pd.Series(np.nan, index=idx)
        feats[f"missing_{c}"] = feats[c].isna().astype(float)

    # Baseline ingredients (EWMA level and day-of-week offset), causal.
    # The weekday offset is the average residual against the level *before* that day,
    # shrunk toward 0 when a weekday has few samples (n / (n + DOW_SHRINKAGE)).
    hl = pd.Timedelta(days=spec.baseline_half_life_days)
    tdow = (idx + pd.Timedelta(days=1)).dayofweek.to_numpy()
    rows = np.arange(len(idx))
    ldow = pd.DatetimeIndex(logged.index).dayofweek.to_numpy()
    for f in TARGETS:
        s = logged[f].astype(float)
        ewma = (
            s.ewm(halflife=hl, times=pd.DatetimeIndex(s.index)).mean()  # type: ignore[arg-type]
            if len(s)
            else s
        )
        feats[f"base_ewma_{f}"] = ewma.reindex(idx).ffill()
        feats[f"base_mean_{f}"] = cal[f].astype(float).expanding(min_periods=1).mean().ffill()
        resid = (s - ewma.shift(1)).to_numpy()
        ok = ~np.isnan(resid)
        sums = np.zeros((len(s), 7))
        counts = np.zeros((len(s), 7))
        for d in range(7):
            m = ok & (ldow == d)
            sums[:, d] = np.cumsum(np.where(m, resid, 0.0))
            counts[:, d] = np.cumsum(m)
        sums_c = pd.DataFrame(sums, index=s.index).reindex(idx).ffill().fillna(0.0).to_numpy()
        counts_c = pd.DataFrame(counts, index=s.index).reindex(idx).ffill().fillna(0.0).to_numpy()
        enough = (counts_c >= 2).all(axis=1)
        n_d = counts_c[rows, tdow]
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_d = sums_c[rows, tdow] / n_d
        shrunk = mean_d * n_d / (n_d + DOW_SHRINKAGE)
        offset = np.where(enough, shrunk, 0.0)
        feats[f"base_dowoff_{f}"] = pd.Series(np.nan_to_num(offset), index=idx)

    return pd.DataFrame(feats, index=idx)


def make_targets(daily: pd.DataFrame) -> pd.DataFrame:
    """Value of each target on day t + 1, indexed by origin day t (NaN if not logged)."""
    out = pd.DataFrame(index=daily.index)
    nxt = daily.shift(-1)
    for f in TARGETS:
        out[f] = nxt[f].astype(float).where(nxt["logged"].astype("boolean").fillna(False))
    return out


def training_rows(features: pd.DataFrame, targets: pd.DataFrame, max_gap_days: int) -> pd.Index:
    """Origin days usable for training: target known and data not too stale."""
    ok = targets["mood"].notna() & (features["days_since_last_log"] <= max_gap_days)
    return features.index[ok.to_numpy()]
