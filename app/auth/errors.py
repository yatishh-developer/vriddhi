from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ApiError(HTTPException):
    """A stable, request-safe API failure."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message


async def auth_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
        headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
    )


class AuthError(ApiError):
    """Authentication/authorization failure with a stable public code."""


class DomainError(ApiError):
    """Checkout and inventory failure with a stable public code."""


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return await auth_error_handler(request, exc)
