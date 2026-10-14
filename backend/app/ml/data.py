"""Turn check-in records into a calendar-indexed daily frame.

The frame has one row per calendar day from the first logged day to ``through``
(inclusive). Days without a check-in have ``logged == False`` and NaN values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from app.ml.schema import CORE_FEELINGS, OPTIONAL_NUMERIC

CheckInRecord = Mapping[str, Any]


def custom_metric_column(metric_id: int | str) -> str:
    return f"cm_{metric_id}"


def records_to_daily(records: Iterable[CheckInRecord], through: date | None = None) -> pd.DataFrame:
    """Build the daily frame.

    Each record needs ``date`` and the core feelings. Optional keys: the optional
    numeric fields, ``tags`` (list of str) and ``custom`` (mapping metric id -> value).
    Notes are deliberately ignored: v1 never models free text.
    """
    rows: list[dict[str, Any]] = []
    for r in records:
        row: dict[str, Any] = {"date": pd.Timestamp(r["date"])}
        for f in CORE_FEELINGS:
            row[f] = float(r[f])
        for f in OPTIONAL_NUMERIC:
            v = r.get(f)
            row[f] = float(v) if v is not None else np.nan
        row["tags"] = [str(t).lower() for t in (r.get("tags") or [])]
        for mid, val in (r.get("custom") or {}).items():
            row[custom_metric_column(mid)] = float(val) if val is not None else np.nan
        rows.append(row)

    columns = ["logged", *CORE_FEELINGS, *OPTIONAL_NUMERIC, "tags"]
    if not rows:
        return pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], name="date"))

    df = pd.DataFrame(rows).drop_duplicates("date", keep="last").set_index("date").sort_index()
    if through is not None:
        df = df[df.index <= pd.Timestamp(through)]
        if df.empty:
            return pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], name="date"))
    start = df.index.min()
    end = pd.Timestamp(through) if through is not None else df.index.max()
    idx = pd.date_range(start, end, freq="D", name="date")
    logged_dates = df.index
    df = df.reindex(idx)
    df["logged"] = df.index.isin(logged_dates)
    df["tags"] = [t if isinstance(t, list) else [] for t in df["tags"]]
    cm_cols = sorted(c for c in df.columns if str(c).startswith("cm_"))
    ordered = [*columns, *cm_cols]
    return df[ordered]


def extend_to(daily: pd.DataFrame, through: date) -> pd.DataFrame:
    """Extend (or truncate) the calendar to ``through`` with unlogged days."""
    end = pd.Timestamp(through)
    if daily.empty:
        return daily
    if end <= daily.index.max():
        return daily[daily.index <= end]
    idx = pd.date_range(daily.index.min(), end, freq="D", name="date")
    out = daily.reindex(idx)
    out["logged"] = out["logged"].astype("boolean").fillna(False).astype(bool)
    out["tags"] = [t if isinstance(t, list) else [] for t in out["tags"]]
    return out


def days_logged(daily: pd.DataFrame) -> int:
    if daily.empty:
        return 0
    return int(daily["logged"].sum())
