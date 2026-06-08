import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse

from core.config import settings


# Simple in-memory rate limiter.
# For multi-worker production deployments, replace with Redis-based limiting.
_request_log: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT = settings.RATE_LIMIT_REQUESTS
WINDOW_SECONDS = settings.RATE_LIMIT_WINDOW_SECONDS


async def rate_limit_middleware(request: Request, call_next):
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = (
        forwarded_for.split(",")[0].strip()
        or request.headers.get("cf-connecting-ip")
        or (request.client.host if request.client else "unknown")
    )
    current_time = time.time()

    # Prune timestamps outside the window
    _request_log[client_ip] = [
        ts for ts in _request_log[client_ip]
        if current_time - ts < WINDOW_SECONDS
    ]

    if len(_request_log[client_ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
        )

    _request_log[client_ip].append(current_time)

    response = await call_next(request)
    return response
