from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.limiter import limiter
from app.db.base import Base
from app.db.migrations import (
    ensure_channel_and_hold_tables,
    ensure_crm_lead_enhancements,
    ensure_governance_and_outbox_tables,
    ensure_notification_ledger_table,
    ensure_security_and_idempotency_tables,
    ensure_vehicle_lifecycle_and_audit_columns,
)
from app.db.session import engine
import app.models  # noqa: F401
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.logging import CorrelationIdMiddleware


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("Startup table creation notice: %s", exc)

    for migration in (
        ensure_security_and_idempotency_tables,
        ensure_channel_and_hold_tables,
        ensure_vehicle_lifecycle_and_audit_columns,
        ensure_crm_lead_enhancements,
        ensure_notification_ledger_table,
        ensure_governance_and_outbox_tables,
    ):
        try:
            migration(engine)
        except Exception as exc:
            logger.warning(
                "Startup schema verification notice (%s): %s",
                migration.__name__,
                exc,
            )
    logger.info("DealerDesk backend server started successfully")
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

app.state.limiter = limiter

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(IdempotencyMiddleware)

# Exception handlers (centralized enterprise error envelope)
register_exception_handlers(app)

# API Routers
app.include_router(api_router)

# Also expose direct channel route aliases for webhook convenience
from app.channels.vapi.router import router as direct_vapi_router
from app.channels.whatsapp.router import router as direct_whatsapp_router
app.include_router(
    direct_whatsapp_router,
    prefix="/channels/whatsapp",
    tags=["WhatsApp Channel"],
)
app.include_router(
    direct_vapi_router,
    prefix="/channels/vapi",
    tags=["Vapi Voice Channel"],
)


@app.get(
    "/",
    tags=["System"],
    summary="Get API status",
    description="Confirms that the DealerDesk backend is available.",
    response_description="Current API status",
)
async def read_root() -> dict[str, str]:
    return {"message": "DealerDesk backend is running"}
