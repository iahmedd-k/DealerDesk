from collections.abc import Mapping
from datetime import datetime, timezone
from http import HTTPStatus
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAPI Error Schema
# ---------------------------------------------------------------------------

class ErrorResponseEnvelope(BaseModel):
    detail: Any
    error_code: str
    request_id: str | None = None
    timestamp: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Requested resource was not found",
                "error_code": "NOT_FOUND",
                "request_id": "fe-1718000000-abc123",
                "timestamp": "2026-11-21T12:00:00Z",
            }
        }
    )


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class ApplicationError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        detail: str,
        *,
        error_code: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        if error_code is not None:
            self.error_code = error_code
        self.headers = dict(headers) if headers is not None else None


class BadRequestError(ApplicationError):
    status_code = 400
    error_code = "BAD_REQUEST"


class UnauthorizedError(ApplicationError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(ApplicationError):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundError(ApplicationError):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(ApplicationError):
    status_code = 409
    error_code = "CONFLICT"


class PayloadTooLargeError(ApplicationError):
    status_code = 413
    error_code = "PAYLOAD_TOO_LARGE"


class UnsupportedMediaTypeError(ApplicationError):
    status_code = 415
    error_code = "UNSUPPORTED_MEDIA_TYPE"


class UnprocessableEntityError(ApplicationError):
    status_code = 422
    error_code = "UNPROCESSABLE_ENTITY"


class TooManyRequestsError(ApplicationError):
    status_code = 429
    error_code = "TOO_MANY_REQUESTS"


class BadGatewayError(ApplicationError):
    status_code = 502
    error_code = "BAD_GATEWAY"


class ServiceUnavailableError(ApplicationError):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Standard Error Response Builder
# ---------------------------------------------------------------------------

def build_error_response(
    request: Request,
    status_code: int,
    detail: Any,
    error_code: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Builds a standardized, enterprise-grade JSON error envelope."""
    if error_code is None:
        try:
            error_code = HTTPStatus(status_code).name
        except ValueError:
            error_code = "HTTP_ERROR"

    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    content: dict[str, Any] = {
        "detail": detail,
        "error_code": error_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if request_id:
        content["request_id"] = str(request_id)

    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = str(request_id)

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=response_headers,
    )


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

async def application_error_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    """Handles domain-specific ApplicationError exceptions."""
    return build_error_response(
        request=request,
        status_code=exc.status_code,
        detail=exc.detail,
        error_code=exc.error_code,
        headers=exc.headers,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException | HTTPException,
) -> JSONResponse:
    """Handles FastAPI and Starlette HTTPException instances."""
    return build_error_response(
        request=request,
        status_code=exc.status_code,
        detail=exc.detail,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handles Pydantic request body and query validation errors."""
    errors = exc.errors()
    # Format readable single-line detail message while keeping structured issues
    if errors:
        first_error = errors[0]
        loc = " -> ".join(str(item) for item in first_error.get("loc", []))
        msg = first_error.get("msg", "Invalid value")
        detail = f"Validation failed at '{loc}': {msg}"
    else:
        detail = "Request validation failed"

    return build_error_response(
        request=request,
        status_code=422,
        detail=detail,
        error_code="UNPROCESSABLE_ENTITY",
    )


async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Handles SlowAPI rate limit exceeded events."""
    return build_error_response(
        request=request,
        status_code=429,
        detail=f"Rate limit exceeded: {exc.detail}",
        error_code="TOO_MANY_REQUESTS",
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all handler for unexpected internal server errors."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    logger.exception(
        "Unhandled server exception during request processing",
        extra={"request_id": request_id, "path": request.url.path},
        exc_info=exc,
    )
    return build_error_response(
        request=request,
        status_code=500,
        detail="An internal server error occurred.",
        error_code="INTERNAL_SERVER_ERROR",
    )


# ---------------------------------------------------------------------------
# Central Registration
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Registers all global exception handlers on the FastAPI application."""
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
