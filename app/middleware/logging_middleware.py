import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger("vriddhi.access")


class LoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time

        logger.info(
            "%s %s %d %.4fs",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )

        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        return response
