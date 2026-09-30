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
AUTH_RATE_LIMIT = settings.AUTH_RATE_LIMIT_REQUESTS
AUTH_WINDOW_SECONDS = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
AUTH_PATHS = {
    "/auth/login",
    "/auth/signup",
    "/staff/auth/verify-invite-code",
    "/staff/auth/verify",
    "/auth/staff/verify-invite-code",
    "/staff/auth/firebase-login",
    "/staff/auth/accept-invite",
    "/staff/auth/refresh",
}


async def rate_limit_middleware(request: Request, call_next):
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = (
        forwarded_for.split(",")[0].strip()
        or request.headers.get("cf-connecting-ip")
        or (request.client.host if request.client else "unknown")
    )
    current_time = time.time()

    is_auth_request = request.url.path in AUTH_PATHS
    limit = AUTH_RATE_LIMIT if is_auth_request else RATE_LIMIT
    window = AUTH_WINDOW_SECONDS if is_auth_request else WINDOW_SECONDS
    key = f"auth:{client_ip}" if is_auth_request else f"global:{client_ip}"
    runtime = getattr(request.app.state, "redis_runtime", None)
    if runtime and runtime.enabled:
        try:
            count = await runtime.increment(f"rate:{key}:{int(current_time // window)}", window)
            if count > limit:
                return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again later."})
        except Exception:
            # Authentication/credential endpoints fail closed when the
            # configured distributed limiter is unavailable. General traffic
            # keeps its development-compatible local fallback.
            if is_auth_request:
                return JSONResponse(status_code=503, content={"detail": "Authentication rate limiter unavailable."})
            runtime = None

    if runtime and runtime.enabled:
        return await call_next(request)

    _request_log[key] = [ts for ts in _request_log[key] if current_time - ts < window]

    if len(_request_log[key]) >= limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
        )

    _request_log[key].append(current_time)

    response = await call_next(request)
    return response
