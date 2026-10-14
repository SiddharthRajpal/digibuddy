"""Logging setup.

Privacy rule: never log check-in values or notes. Request logging records only
method, route template, status code, user id and timing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

logger = logging.getLogger("digibuddy")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def request_timing_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    user_id = getattr(request.state, "user_id", None)
    logger.info(
        "request method=%s route=%s status=%s user_id=%s ms=%.1f",
        request.method,
        path,
        response.status_code,
        user_id,
        elapsed_ms,
    )
    return response
