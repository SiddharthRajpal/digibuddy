from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_TMP = tempfile.mkdtemp(prefix="digibuddy-tests-")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("MODEL_ARTIFACT_DIR", str(Path(_TMP) / "artifacts"))
os.environ.setdefault("AUTH_RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/unused.db")

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402

from app.api.deps import get_now  # noqa: E402
from app.core.rate_limit import auth_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import set_engine  # noqa: E402
from app.main import create_app  # noqa: E402


class Clock:
    """Mutable clock injected into the API (UTC)."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 14, 4, 0, tzinfo=UTC)  # 12:00 in Singapore

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest_asyncio.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    set_engine(eng)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine: AsyncEngine, clock: Clock) -> AsyncIterator[httpx.AsyncClient]:
    auth_limiter.reset()
    app = create_app()
    app.dependency_overrides[get_now] = clock
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def signup(
    client: httpx.AsyncClient,
    email: str = "a@example.com",
    tz: str = "Asia/Singapore",
    password: str = "password123",
) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "display_name": "Sid", "timezone": tz},
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def checkin_payload(d: str | None = None, mood: int = 6, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "mood": mood,
        "energy": 6,
        "stress": 4,
        "anxiety": 3,
        "focus": 6,
        "sleep_hours": 7.5,
        "tags": ["Exam"],
        **extra,
    }
    if d is not None:
        body["date"] = d
    return body


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    auth_limiter.reset()
    yield
