from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.checkins import router as checkins_router
from app.api.me import router as me_router
from app.api.other import meta_router, metrics_router, predictions_router, twin_router
from app.core.config import get_settings
from app.core.logging import configure_logging, request_timing_middleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    configure_logging(s.log_level)
    scheduler = None
    if s.enable_scheduler:
        from app.jobs.retrain import start_scheduler

        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="DigiBuddy API",
        version=s.app_version,
        description=(
            "A personal digital twin for emotional wellbeing. "
            "Not a medical device; see GET /api/v1/meta."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_timing_middleware)
    api = APIRouter(prefix="/api/v1")
    for r in (
        auth_router,
        me_router,
        checkins_router,
        metrics_router,
        predictions_router,
        twin_router,
        meta_router,
    ):
        api.include_router(r)
    app.include_router(api)
    return app


app = create_app()
