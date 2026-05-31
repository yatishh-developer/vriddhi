import logging

from fastapi import Request
from fastapi.responses import JSONResponse


logger = logging.getLogger("vriddhi.errors")


async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a safe 500 response.

    Internal error details are logged but NOT exposed to the client
    in production to avoid leaking sensitive information.
    """
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": "An internal server error occurred. Please try again later.",
        },
    )
