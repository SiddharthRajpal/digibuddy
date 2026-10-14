"""Timezones, authorization, support triggers, account deletion, nightly job, insights."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.clock import local_date
from app.core.support_resources import region_for_timezone
from app.db.models import (
    CustomMetric,
    CustomMetricValue,
    DailyCheckIn,
    ModelVersion,
    Prediction,
    User,
)
from app.jobs.retrain import run_nightly
from app.ml.data import records_to_daily
from app.services.insights import compute_insights
from app.services.support import support_reasons
from app.services.users import user_artifact_dir
from scripts.generate_synthetic import generate_user
from tests.conftest import Clock, auth, checkin_payload, signup

# --- timezone ----------------------------------------------------------------------------


def test_local_date_uses_user_timezone() -> None:
    # 23:30 in Singapore on 14 Oct is 15:30 UTC on 14 Oct.
    now = datetime(2026, 10, 14, 15, 30, tzinfo=UTC)
    assert local_date("Asia/Singapore", now) == date(2026, 10, 14)
    # 16:30 UTC is already 00:30 on 15 Oct in Singapore, but still 14 Oct in London.
    later = datetime(2026, 10, 14, 16, 30, tzinfo=UTC)
    assert local_date("Asia/Singapore", later) == date(2026, 10, 15)
    assert local_date("Europe/London", later) == date(2026, 10, 14)


async def test_checkin_at_2330_singapore_lands_on_local_date(
    client: httpx.AsyncClient, clock: Clock
) -> None:
    h = auth((await signup(client, tz="Asia/Singapore"))["access_token"])
    clock.now = datetime(2026, 10, 14, 15, 30, tzinfo=UTC)  # 23:30 SGT
    r = await client.post("/api/v1/checkins", headers=h, json=checkin_payload())
    assert r.json()["checkin"]["date"] == "2026-10-14"
    clock.now = datetime(2026, 10, 14, 16, 30, tzinfo=UTC)  # 00:30 SGT next day
    r = await client.post("/api/v1/checkins", headers=h, json=checkin_payload())
    assert r.json()["checkin"]["date"] == "2026-10-15"


# --- authorization -----------------------------------------------------------------------


async def test_user_cannot_touch_another_users_data(client: httpx.AsyncClient) -> None:
    a = auth((await signup(client, "a@example.com"))["access_token"])
    b = auth((await signup(client, "b@example.com"))["access_token"])
    await client.post("/api/v1/checkins", headers=a, json=checkin_payload(notes="A's secret"))
    mid = (
        await client.post(
            "/api/v1/metrics", headers=a, json={"name": "Practice", "min": 0, "max": 5}
        )
    ).json()["id"]

    assert (await client.get("/api/v1/checkins", headers=b)).json() == []
    assert (await client.get("/api/v1/checkins/2026-10-14", headers=b)).status_code == 404
    assert (
        await client.patch("/api/v1/checkins/2026-10-14", headers=b, json={"mood": 1})
    ).status_code == 404
    assert (await client.delete("/api/v1/checkins/2026-10-14", headers=b)).status_code == 404
    assert (
        await client.patch(f"/api/v1/metrics/{mid}", headers=b, json={"name": "x"})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/metrics/{mid}", headers=b)).status_code == 404
    # B cannot attach values to A's tracker either.
    body = checkin_payload(custom_metrics=[{"metric_id": mid, "value": 1}])
    assert (await client.post("/api/v1/checkins", headers=b, json=body)).status_code == 422
    export_b = (await client.get("/api/v1/me/export", headers=b)).json()
    assert export_b["checkins"] == [] and export_b["custom_metrics"] == []

    # A's data is untouched.
    r = await client.get("/api/v1/checkins/2026-10-14", headers=a)
    assert r.status_code == 200 and r.json()["mood"] == 6


async def test_tampered_or_wrong_type_tokens_rejected(client: httpx.AsyncClient) -> None:
    data = await signup(client)
    token = data["access_token"]
    assert (await client.get("/api/v1/me", headers=auth(token + "x"))).status_code == 401
    refresh = client.cookies.get("digibuddy_refresh")
    assert refresh
    assert (await client.get("/api/v1/me", headers=auth(refresh))).status_code == 401


# --- support -----------------------------------------------------------------------------


def _ci(d: date, mood: int) -> DailyCheckIn:
    return cast(DailyCheckIn, SimpleNamespace(date=d, mood=mood))


def test_support_reasons_each_condition() -> None:
    d = date(2026, 10, 14)
    assert support_reasons([_ci(d, 5)], d, 6.0) == []
    assert support_reasons([_ci(d, 2)], d, None) == ["very_low_mood"]
    assert support_reasons([_ci(d, 3)], d, None) == []
    streak = [_ci(d - timedelta(days=2), 3), _ci(d - timedelta(days=1), 3), _ci(d, 3)]
    assert support_reasons(streak, d, None) == ["low_mood_streak"]
    broken = [_ci(d - timedelta(days=2), 3), _ci(d, 3)]  # a gap breaks the streak
    assert support_reasons(broken, d, None) == []
    not_low = [_ci(d - timedelta(days=2), 3), _ci(d - timedelta(days=1), 4), _ci(d, 3)]
    assert support_reasons(not_low, d, None) == []
    assert support_reasons([_ci(d, 6)], d, 3.0) == ["low_forecast"]
    assert support_reasons([_ci(d, 6)], d, 3.1) == []
    assert support_reasons([], None, 2.5) == ["low_forecast"]


def test_support_region_from_timezone() -> None:
    assert region_for_timezone("Asia/Singapore") == "SG"
    assert region_for_timezone("Asia/Kolkata") == "IN"
    assert region_for_timezone("Europe/Paris") == "INTL"


async def test_support_object_in_checkin_response(client: httpx.AsyncClient) -> None:
    h = auth((await signup(client, tz="Asia/Singapore"))["access_token"])
    r = (await client.post("/api/v1/checkins", headers=h, json=checkin_payload(mood=6))).json()
    assert r["support"] is None
    r = (await client.post("/api/v1/checkins", headers=h, json=checkin_payload(mood=2))).json()
    s = r["support"]
    assert s["reasons"] == ["very_low_mood"]
    assert s["region"] == "SG"
    phones = {res["phone"] for res in s["resources"]}
    assert {"1767", "6389 2222"} <= phones
    # The Today page sees it too, even while still collecting the first week.
    t = (await client.get("/api/v1/predictions/tomorrow", headers=h)).json()
    assert t["status"] == "collecting"
    assert t["support"]["reasons"] == ["very_low_mood"]


async def test_support_on_three_low_days_india(client: httpx.AsyncClient, clock: Clock) -> None:
    h = auth((await signup(client, tz="Asia/Kolkata"))["access_token"])
    for i, mood in enumerate([3, 3, 3]):
        d = date(2026, 10, 12) + timedelta(days=i)
        r = await client.post(
            "/api/v1/checkins", headers=h, json=checkin_payload(d.isoformat(), mood)
        )
    s = r.json()["support"]
    assert s["reasons"] == ["low_mood_streak"]
    assert s["region"] == "IN"
    assert any(res["phone"] == "14416" for res in s["resources"])


# --- delete account ----------------------------------------------------------------------


async def test_delete_account_removes_rows_and_artifacts(
    client: httpx.AsyncClient, engine: AsyncEngine, clock: Clock
) -> None:
    data = await signup(client, tz="UTC")
    h = auth(data["access_token"])
    uid = data["user"]["id"]
    mid = (
        await client.post(
            "/api/v1/metrics", headers=h, json={"name": "Practice", "min": 0, "max": 5}
        )
    ).json()["id"]
    start = date(2026, 9, 1)
    for i in range(9):
        d = start + timedelta(days=i)
        clock.now = datetime(d.year, d.month, d.day, 12, tzinfo=UTC)
        body = checkin_payload(mood=4 + i % 3, custom_metrics=[{"metric_id": mid, "value": 2}])
        assert (await client.post("/api/v1/checkins", headers=h, json=body)).status_code == 201
    other = auth((await signup(client, "other@example.com"))["access_token"])
    await client.post("/api/v1/checkins", headers=other, json=checkin_payload())

    art_dir: Path = user_artifact_dir(uid)
    assert art_dir.exists() and any(art_dir.iterdir())

    sm = async_sessionmaker(engine)

    async def counts() -> dict[str, int]:
        async with sm() as s:
            out = {}
            for model in (
                User,
                DailyCheckIn,
                CustomMetric,
                CustomMetricValue,
                Prediction,
                ModelVersion,
            ):
                out[model.__name__] = int(
                    await s.scalar(select(func.count()).select_from(model)) or 0
                )
            return out

    before = await counts()
    assert before["Prediction"] > 0 and before["ModelVersion"] > 0

    r = await client.delete("/api/v1/me", headers=h)
    assert r.status_code == 204
    after = await counts()
    assert after == {
        "User": 1,
        "DailyCheckIn": 1,
        "CustomMetric": 0,
        "CustomMetricValue": 0,
        "Prediction": 0,
        "ModelVersion": 0,
    }
    assert not art_dir.exists()
    assert (await client.get("/api/v1/me", headers=h)).status_code == 401


# --- nightly job -------------------------------------------------------------------------


async def test_nightly_job_runs_at_3am_local_only_when_new_data(
    client: httpx.AsyncClient, engine: AsyncEngine, clock: Clock
) -> None:
    h = auth((await signup(client, tz="Asia/Singapore"))["access_token"])
    start = date(2026, 10, 1)
    for i in range(8):
        d = start + timedelta(days=i)
        clock.now = datetime(d.year, d.month, d.day, 12, tzinfo=UTC)  # 20:00 SGT
        await client.post("/api/v1/checkins", headers=h, json=checkin_payload(mood=5 + i % 2))

    noon_sgt = datetime(2026, 10, 9, 4, 0, tzinfo=UTC)
    three_am_sgt = datetime(2026, 10, 8, 19, 0, tzinfo=UTC)  # 03:00 SGT on 9 Oct
    assert await run_nightly(noon_sgt) == 0
    # First time at 03:00 local: the check-in on day 8 is newer than the first training.
    assert await run_nightly(three_am_sgt) == 1
    # Nothing new since -> skipped.
    assert await run_nightly(three_am_sgt + timedelta(minutes=1)) == 0

    sm = async_sessionmaker(engine)
    async with sm() as s:
        active = (await s.scalars(select(ModelVersion).where(ModelVersion.is_active))).all()
        assert {mv.target for mv in active} == {"mood", "energy", "stress"}
        assert all(mv.trained_through == date(2026, 10, 8) for mv in active)
        p = await s.scalar(select(Prediction).where(Prediction.target_date == date(2026, 10, 9)))
        assert p is not None and p.mood_actual is None


# --- insights ----------------------------------------------------------------------------


def test_insights_are_observations_with_sample_sizes() -> None:
    recs: list[dict[str, Any]] = generate_user("strong", 120, start=date(2026, 1, 1), seed=1)
    for r in recs:
        r["notes"] = "this text must never matter"
    items = compute_insights(records_to_daily(recs))
    kinds = {i.kind for i in items}
    assert {"correlation", "weekday", "tag"} <= kinds
    for i in items:
        assert "n = " in i.text
        assert "because" not in i.text.lower() and "causes" not in i.text.lower()
        if i.kind == "correlation":
            assert i.n >= 21 and i.r is not None and abs(i.r) >= 0.3
    sleep = [i for i in items if i.factor == "sleep_hours"]
    assert sleep and sleep[0].direction == "higher"


def test_insights_need_enough_data() -> None:
    recs = generate_user("strong", 15, start=date(2026, 1, 1), seed=1)
    items = compute_insights(records_to_daily(recs))
    assert [i for i in items if i.kind in ("correlation", "weekday")] == []


def test_notes_are_not_part_of_ml_frame() -> None:
    recs = generate_user("weak", 10, start=date(2026, 1, 1), seed=1)
    recs[0]["notes"] = "secret"
    daily = records_to_daily(recs)
    assert "notes" not in daily.columns
    assert isinstance(daily, pd.DataFrame)
