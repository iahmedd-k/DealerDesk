from collections.abc import Mapping

from fastapi import Request
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    status_code = 500

    def __init__(
        self,
        detail: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.headers = dict(headers) if headers is not None else None


class BadRequestError(ApplicationError):
    status_code = 400


class UnauthorizedError(ApplicationError):
    status_code = 401


class ForbiddenError(ApplicationError):
    status_code = 403


class NotFoundError(ApplicationError):
    status_code = 404


class ConflictError(ApplicationError):
    status_code = 409


class PayloadTooLargeError(ApplicationError):
    status_code = 413


class UnsupportedMediaTypeError(ApplicationError):
    status_code = 415


class UnprocessableEntityError(ApplicationError):
    status_code = 422


class BadGatewayError(ApplicationError):
    status_code = 502


class ServiceUnavailableError(ApplicationError):
    status_code = 503


async def application_error_handler(
    _: Request,
    error: ApplicationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail},
        headers=error.headers,
    )
