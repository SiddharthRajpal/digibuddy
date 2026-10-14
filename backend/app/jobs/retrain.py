"""Nightly retraining.

``run_nightly`` is a plain async function so it can be called from any scheduler or
queue. ``start_scheduler`` wires it to APScheduler, running at minute 0 of every hour
and picking the users whose local time is the configured nightly hour (03:00).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.clock import local_date, local_hour, utcnow
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_sessionmaker
from app.services.twin import generate_prediction, needs_retrain, retrain

logger = logging.getLogger(__name__)


async def retrain_user(user_id: int, now: datetime, force: bool = False) -> bool:
    """Retrain one user if they logged anything new, then refresh today's forecast."""
    async with get_sessionmaker()() as session:
        user = await session.get(User, user_id)
        if user is None:
            return False
        if not force and not await needs_retrain(session, user):
            return False
        today = local_date(user.timezone, now)
        yesterday = today - timedelta(days=1)
        await retrain(session, user, as_of=yesterday, now=now)
        # The forecast for today (made from data through yesterday) gets the new model.
        await generate_prediction(session, user, yesterday, now)
        return True


async def run_nightly(now: datetime | None = None, hour: int | None = None) -> int:
    now = now or utcnow()
    hour = get_settings().nightly_hour_local if hour is None else hour
    async with get_sessionmaker()() as session:
        users = (await session.execute(select(User.id, User.timezone))).all()
    due = [uid for uid, tz in users if local_hour(tz, now) == hour]
    done = 0
    for uid in due:
        try:
            done += int(await retrain_user(uid, now))
        except Exception:
            logger.exception("nightly retrain failed user_id=%s", uid)
    logger.info("nightly run due=%s retrained=%s", len(due), done)
    return done


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_nightly, "cron", minute=0, id="nightly-retrain", coalesce=True)
    scheduler.start()
    return scheduler
