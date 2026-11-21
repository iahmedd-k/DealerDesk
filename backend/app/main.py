from collections.abc import AsyncIterator
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.errors import ApplicationError, application_error_handler
from app.db.base import Base
from app.db.migrations import ensure_vehicle_brand_associations, run_alembic_upgrade
from app.db.session import engine
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.logging import CorrelationIdMiddleware
from app.models import TestDriveBooking


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        run_alembic_upgrade("head")
    except Exception:
        Base.metadata.create_all(bind=engine)
        ensure_vehicle_brand_associations(engine)
        active_booking_index = next(
            index
            for index in TestDriveBooking.__table__.indexes
            if index.name == "uq_test_drive_booking_active_customer"
        )
        active_booking_index.create(bind=engine, checkfirst=True)
    logger.info("Server is running")
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="DealerDesk Backend",
    summary="DealerDesk vehicle dealership management API",
    description=(
        "A versioned REST API for DealerDesk. "
        "Authentication uses bearer access tokens."
    ),
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Create accounts and manage authenticated sessions.",
        },
        {
            "name": "System",
            "description": "Service status and operational endpoints.",
        },
    ],
    swagger_ui_parameters={
        "defaultModelsExpandDepth": 1,
        "docExpansion": "list",
        "displayRequestDuration": True,
        "filter": True,
    },
)

settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(IdempotencyMiddleware)

async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc))
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    content: dict[str, object] = {
        "detail": detail,
        "error_code": code_map.get(status_code, "HTTP_ERROR"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if request_id:
        content["request_id"] = str(request_id)
    headers = dict(getattr(exc, "headers", None) or {})
    if request_id:
        headers["X-Request-ID"] = str(request_id)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


app.add_exception_handler(ApplicationError, application_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.include_router(api_router)


@app.get(
    "/",
    tags=["System"],
    summary="Get API status",
    description="Confirms that the DealerDesk backend is available.",
    response_description="Current API status",
)
async def read_root() -> dict[str, str]:
    return {"message": "DealerDesk backend is running"}
