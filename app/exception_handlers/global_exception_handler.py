import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger("vriddhi.errors")


async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a safe 500 response.

    Internal error details are logged but NOT exposed to the client
    in production to avoid leaking sensitive information.
    """
    logger.exception(
        "Unhandled exception request_id=%s on %s %s",
        getattr(request.state, "request_id", "unknown"),
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred. Please try again later.",
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )


async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Keep malformed v1 checkout requests in the standard error envelope."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )
