"""API integration tests: auth, me, check-ins, metrics, predictions, twin, insights, meta."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx

from app.core.config import get_settings
from app.core.rate_limit import auth_limiter
from tests.conftest import Clock, auth, checkin_payload, signup


async def test_health_is_public(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_protected_endpoints_require_auth(client: httpx.AsyncClient) -> None:
    for path in [
        "/api/v1/me",
        "/api/v1/checkins",
        "/api/v1/twin",
        "/api/v1/insights",
        "/api/v1/meta",
        "/api/v1/predictions/tomorrow",
        "/api/v1/metrics",
    ]:
        r = await client.get(path)
        assert r.status_code == 401, path


async def test_signup_login_refresh_logout(client: httpx.AsyncClient) -> None:
    data = await signup(client)
    assert data["user"]["timezone"] == "Asia/Singapore"
    assert data["user"]["onboarding_completed"] is False
    assert "digibuddy_refresh" in client.cookies

    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "A@example.com",
            "password": "password123",
            "display_name": "x",
            "timezone": "Asia/Singapore",
        },
    )
    assert r.status_code == 409

    r = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "nope"})
    assert r.status_code == 401
    r = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "password123"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert (await client.get("/api/v1/me", headers=auth(token))).status_code == 200

    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    assert r.json()["access_token"]

    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    # Old access tokens are revoked by logout.
    assert (await client.get("/api/v1/me", headers=auth(token))).status_code == 401
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_signup_rejects_bad_timezone_and_short_password(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "b@example.com",
            "password": "password123",
            "display_name": "B",
            "timezone": "Mars/Olympus",
        },
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "b@example.com",
            "password": "short",
            "display_name": "B",
            "timezone": "UTC",
        },
    )
    assert r.status_code == 422


async def test_auth_rate_limit(client: httpx.AsyncClient) -> None:
    settings = get_settings()
    old = settings.auth_rate_limit_per_minute
    settings.auth_rate_limit_per_minute = 3
    auth_limiter.reset()
    try:
        codes = [
            (
                await client.post(
                    "/api/v1/auth/login", json={"email": "x@example.com", "password": "p"}
                )
            ).status_code
            for _ in range(5)
        ]
    finally:
        settings.auth_rate_limit_per_minute = old
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


async def test_patch_me_and_meta(client: httpx.AsyncClient) -> None:
    token = (await signup(client))["access_token"]
    r = await client.patch(
        "/api/v1/me",
        headers=auth(token),
        json={
            "display_name": "Siddharth",
            "timezone": "Asia/Kolkata",
            "onboarding_completed": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Siddharth"
    assert r.json()["timezone"] == "Asia/Kolkata"
    assert r.json()["onboarding_completed"] is True
    r = await client.patch("/api/v1/me", headers=auth(token), json={"timezone": "Nope/Nope"})
    assert r.status_code == 422

    meta = (await client.get("/api/v1/meta", headers=auth(token))).json()
    assert "not a medical device" in meta["disclaimer"]
    assert {"SG", "IN", "INTL"} <= set(meta["support_regions"])


async def test_checkin_crud_and_validation(client: httpx.AsyncClient, clock: Clock) -> None:
    token = (await signup(client))["access_token"]
    h = auth(token)
    r = await client.post("/api/v1/checkins", headers=h, json=checkin_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["checkin"]["date"] == "2026-10-14"
    assert body["checkin"]["tags"] == ["exam"]
    assert body["forecast_tomorrow"] is None  # still collecting

    # Upsert the same day -> 200, values replaced.
    r = await client.post("/api/v1/checkins", headers=h, json=checkin_payload(mood=7))
    assert r.status_code == 200
    assert r.json()["checkin"]["mood"] == 7

    # Future dates and old backfills are rejected; 3 days back is allowed.
    assert (
        await client.post("/api/v1/checkins", headers=h, json=checkin_payload("2026-10-15"))
    ).status_code == 422
    assert (
        await client.post("/api/v1/checkins", headers=h, json=checkin_payload("2026-10-10"))
    ).status_code == 422
    assert (
        await client.post("/api/v1/checkins", headers=h, json=checkin_payload("2026-10-11"))
    ).status_code == 201

    # Required feelings and ranges.
    bad = checkin_payload()
    bad["mood"] = 11
    assert (await client.post("/api/v1/checkins", headers=h, json=bad)).status_code == 422
    bad = checkin_payload()
    del bad["focus"]
    assert (await client.post("/api/v1/checkins", headers=h, json=bad)).status_code == 422
    assert (
        await client.post("/api/v1/checkins", headers=h, json=checkin_payload(notes="x" * 2001))
    ).status_code == 422

    r = await client.get("/api/v1/checkins?from=2026-10-11&to=2026-10-14", headers=h)
    assert [c["date"] for c in r.json()] == ["2026-10-11", "2026-10-14"]
    r = await client.get("/api/v1/checkins/2026-10-11", headers=h)
    assert r.status_code == 200
    r = await client.patch("/api/v1/checkins/2026-10-11", headers=h, json={"mood": 3, "tags": None})
    assert r.status_code == 200
    assert r.json()["mood"] == 3 and r.json()["tags"] == []
    r = await client.patch("/api/v1/checkins/2026-10-11", headers=h, json={"mood": None})
    assert r.status_code == 422
    assert (await client.delete("/api/v1/checkins/2026-10-11", headers=h)).status_code == 204
    assert (await client.get("/api/v1/checkins/2026-10-11", headers=h)).status_code == 404
    assert (await client.delete("/api/v1/checkins/2026-10-11", headers=h)).status_code == 404


async def test_custom_metrics(client: httpx.AsyncClient) -> None:
    h = auth((await signup(client))["access_token"])
    r = await client.post(
        "/api/v1/metrics",
        headers=h,
        json={"name": "Practice", "min": 0, "max": 10, "unit": "hours"},
    )
    assert r.status_code == 201
    mid = r.json()["id"]
    assert (
        await client.post(
            "/api/v1/metrics", headers=h, json={"name": "Practice", "min": 0, "max": 5}
        )
    ).status_code == 409
    assert (
        await client.post("/api/v1/metrics", headers=h, json={"name": "Bad", "min": 5, "max": 1})
    ).status_code == 422
    r = await client.patch(f"/api/v1/metrics/{mid}", headers=h, json={"max": 12})
    assert r.json()["max"] == 12

    body = checkin_payload(custom_metrics=[{"metric_id": mid, "value": 2.5}])
    r = await client.post("/api/v1/checkins", headers=h, json=body)
    assert r.json()["checkin"]["custom_metrics"] == [{"metric_id": mid, "value": 2.5}]
    body = checkin_payload(custom_metrics=[{"metric_id": mid, "value": 99}])
    assert (await client.post("/api/v1/checkins", headers=h, json=body)).status_code == 422
    body = checkin_payload(custom_metrics=[{"metric_id": 9999, "value": 1}])
    assert (await client.post("/api/v1/checkins", headers=h, json=body)).status_code == 422

    assert len((await client.get("/api/v1/metrics", headers=h)).json()) == 1
    assert (await client.delete(f"/api/v1/metrics/{mid}", headers=h)).status_code == 204
    assert (await client.get("/api/v1/metrics", headers=h)).json() == []


async def _log_days(
    client: httpx.AsyncClient, clock: Clock, h: dict[str, str], n: int, start: date
) -> None:
    for i in range(n):
        d = start + timedelta(days=i)
        clock.now = datetime(d.year, d.month, d.day, 12, 0, tzinfo=UTC)
        mood = 4 + (i % 4)
        r = await client.post(
            "/api/v1/checkins", headers=h, json=checkin_payload(mood=mood, sleep_hours=6 + (i % 3))
        )
        assert r.status_code == 201, r.text


async def test_collecting_then_forecast_then_scoring(
    client: httpx.AsyncClient, clock: Clock
) -> None:
    h = auth((await signup(client, tz="UTC"))["access_token"])
    start = date(2026, 9, 1)
    await _log_days(client, clock, h, 6, start)
    r = (await client.get("/api/v1/predictions/tomorrow", headers=h)).json()
    assert r == {
        "status": "collecting",
        "days_logged": 6,
        "days_needed": 1,
        "forecast": None,
        "support": None,
    }

    # Day 7 -> first forecast arrives in the check-in response.
    d7 = start + timedelta(days=6)
    clock.now = datetime(d7.year, d7.month, d7.day, 12, tzinfo=UTC)
    r = await client.post("/api/v1/checkins", headers=h, json=checkin_payload(mood=6))
    fc = r.json()["forecast_tomorrow"]
    assert fc is not None
    assert fc["target_date"] == (d7 + timedelta(days=1)).isoformat()
    for t in ("mood", "energy", "stress"):
        assert 1 <= fc[t]["lower"] <= fc[t]["predicted"] <= fc[t]["upper"] <= 10
        assert fc[t]["factors"], t
    tomorrow = (await client.get("/api/v1/predictions/tomorrow", headers=h)).json()
    assert tomorrow["status"] == "ready"
    assert tomorrow["forecast"]["mood"]["predicted"] == fc["mood"]["predicted"]

    # Next day: the check-in is scored against the forecast.
    d8 = d7 + timedelta(days=1)
    clock.now = datetime(d8.year, d8.month, d8.day, 12, tzinfo=UTC)
    r = (await client.post("/api/v1/checkins", headers=h, json=checkin_payload(mood=5))).json()
    scored = r["scored_prediction"]
    assert scored["mood"]["actual"] == 5
    assert scored["mood"]["abs_error"] == round(abs(fc["mood"]["predicted"] - 5), 2)

    hist = (await client.get("/api/v1/predictions/history", headers=h)).json()["items"]
    assert hist[-1]["target_date"] == d8.isoformat()

    twin = (await client.get("/api/v1/twin", headers=h)).json()
    assert twin["stage"] == 1 and twin["stage_name"] == "baseline"
    assert twin["days_logged"] == 8
    assert twin["days_to_next_stage"] == 13
    assert twin["accuracy"]["mood"]["n_scored"] == 1
    assert len(twin["series"]) == 1
    assert twin["models"]["mood"]["model_type"] in ("naive", "baseline")


async def test_insights_empty_message(client: httpx.AsyncClient) -> None:
    h = auth((await signup(client))["access_token"])
    r = (await client.get("/api/v1/insights", headers=h)).json()
    assert r["items"] == []
    assert "Keep checking in" in r["message"]


async def test_export_json_and_csv(client: httpx.AsyncClient) -> None:
    h = auth((await signup(client))["access_token"])
    await client.post("/api/v1/checkins", headers=h, json=checkin_payload(notes="private"))
    r = await client.get("/api/v1/me/export", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["email"] == "a@example.com"
    assert data["checkins"][0]["notes"] == "private"
    r = await client.get("/api/v1/me/export?format=csv", headers=h)
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("date,mood,energy")
    assert "exam" in r.text
