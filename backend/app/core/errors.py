from collections.abc import Mapping
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    status_code = 500
    error_code = "INTERNAL_SERVER_ERROR"

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


async def application_error_handler(
    request: Request,
    error: ApplicationError,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    content: dict[str, object] = {
        "detail": error.detail,
        "error_code": error.error_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if request_id:
        content["request_id"] = request_id
    headers = dict(error.headers) if error.headers else {}
    if request_id:
        headers["X-Request-ID"] = str(request_id)
    return JSONResponse(
        status_code=error.status_code,
        content=content,
        headers=headers,
    )
