"""Clock and timezone helpers. All "day" boundaries use the user's IANA timezone."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utcnow() -> datetime:
    return datetime.now(UTC)


def is_valid_timezone(tz: str) -> bool:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def local_date(tz: str, now: datetime | None = None) -> date:
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(ZoneInfo(tz)).date()


def local_hour(tz: str, now: datetime | None = None) -> int:
    now = now or utcnow()
    return now.astimezone(ZoneInfo(tz)).hour
