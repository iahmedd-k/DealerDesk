from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.v1.router import router as api_router
from app.db.base import Base
from app.db.session import engine
import app.models.user  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    print("Server is running", flush=True)
    yield


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
