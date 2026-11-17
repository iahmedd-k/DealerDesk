from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.v1.router import router as api_router
from app.db.base import Base
from app.db.migrations import ensure_vehicle_brand_associations
from app.db.session import engine
from app.models import TestDriveBooking
from app.core.errors import ApplicationError, application_error_handler


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    ensure_vehicle_brand_associations(engine)
    active_booking_index = next(
        index
        for index in TestDriveBooking.__table__.indexes
        if index.name == "uq_test_drive_booking_active_customer"
    )
    active_booking_index.create(bind=engine, checkfirst=True)
    print("Server is running", flush=True)
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

app.add_exception_handler(ApplicationError, application_error_handler)
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
