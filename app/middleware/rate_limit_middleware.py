import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse


# Simple in-memory rate limiter.
# For multi-worker production deployments, replace with Redis-based limiting.
_request_log: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT = 120  # max requests per window
WINDOW_SECONDS = 60


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
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
