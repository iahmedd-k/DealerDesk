from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["System"])


@router.get(
    "",
    summary="Check service health",
    description="Returns a successful response when the API is ready to receive requests.",
    response_description="Current service health.",
)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
