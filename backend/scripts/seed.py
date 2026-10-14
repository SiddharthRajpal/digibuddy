"""Create the demo account with 120 days of synthetic data and a realistic history.

The script replays the app day by day, the way it would have run live:

1. each evening the day's check-in is saved and scored against the stored forecast;
2. a forecast for the next day is made with the active models;
3. on retraining nights the models are retrained, backtested and promoted (or not),
   and the next-day forecast is refreshed with the new models.

Retraining runs weekly and whenever the user reaches a new stage (7, 21 and 60 logged
days), which keeps seeding to a couple of minutes. The live app retrains nightly.

Usage::

    python -m scripts.seed                    # demo@digibuddy.app / demo1234
    python -m scripts.seed --all-profiles     # also weak@ and noise@ users
    python -m scripts.seed --create-tables    # create tables without Alembic (dev only)
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.clock import local_date
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import CustomMetric, CustomMetricValue, DailyCheckIn, User
from app.db.session import get_engine, get_sessionmaker
from app.ml.schema import stage_for_days
from app.services.twin import generate_prediction, retrain, score_date
from app.services.users import delete_user
from scripts.generate_synthetic import generate_user

DEMO_PASSWORD = "demo1234"
TIMEZONE = "Asia/Singapore"
STAGE_THRESHOLDS = (7, 21, 60)


def _at(d: date, hour: int, tz: str = TIMEZONE) -> datetime:
    return datetime(d.year, d.month, d.day, hour, 0, tzinfo=ZoneInfo(tz)).astimezone(UTC)


async def seed_user(
    email: str,
    display_name: str,
    profile: str,
    seed: int,
    days: int = 120,
    retrain_every: int = 7,
) -> None:
    started = time.perf_counter()
    sm = get_sessionmaker()
    today = local_date(TIMEZONE)
    start = today - timedelta(days=days)

    async with sm() as session:
        old = await session.scalar(select(User).where(User.email == email))
        if old is not None:
            await delete_user(session, old)

    async with sm() as session:
        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            display_name=display_name,
            timezone=TIMEZONE,
            onboarding_completed=True,
            token_version=0,
        )
        session.add(user)
        await session.flush()
        practice = CustomMetric(user_id=user.id, name="Practice hours", min=0, max=8, unit="h")
        session.add(practice)
        await session.commit()
        await session.refresh(user)

        records = {r["date"]: r for r in generate_user(profile, days, start=start, seed=seed)}
        rng = random.Random(seed)
        logged = 0
        last_train_logged = 0
        for i in range(days):
            d = start + timedelta(days=i)
            rec = records.get(d)
            if rec is not None:
                fields = {k: v for k, v in rec.items() if k != "date"}
                c = DailyCheckIn(user_id=user.id, date=d, **fields)
                if rng.random() < 0.8:
                    c.metric_values = [
                        CustomMetricValue(metric_id=practice.id, value=round(rng.uniform(0, 4), 1))
                    ]
                session.add(c)
                await session.commit()
                await session.refresh(c)
                await score_date(session, user, d, c)
                logged += 1

            if stage_for_days(logged) > 0:
                await generate_prediction(session, user, d, _at(d, 21))
                crossed = any(last_train_logged < t <= logged for t in STAGE_THRESHOLDS)
                if crossed or logged - last_train_logged >= retrain_every:
                    night = _at(d + timedelta(days=1), 3)
                    await retrain(session, user, as_of=d, now=night)
                    await generate_prediction(session, user, d, night)
                    last_train_logged = logged
    print(
        f"seeded {email}: {logged} check-ins over {days} days "
        f"in {time.perf_counter() - started:.0f}s"
    )


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all-profiles", action="store_true")
    ap.add_argument("--create-tables", action="store_true")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--retrain-every", type=int, default=7)
    args = ap.parse_args()

    if args.create_tables:
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    await seed_user("demo@digibuddy.app", "Demo", "strong", 7, args.days, args.retrain_every)
    if args.all_profiles:
        await seed_user(
            "weak@digibuddy.app", "Weak signal", "weak", 3, args.days, args.retrain_every
        )
        await seed_user("noise@digibuddy.app", "Noise", "noise", 0, args.days, args.retrain_every)
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
