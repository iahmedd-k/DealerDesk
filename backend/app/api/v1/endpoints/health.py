from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.health_service import get_health_report

router = APIRouter(prefix="/health", tags=["System"])


@router.get(
    "",
    summary="Check service health",
    description="Deep health check verifying backend runtime, database connectivity, and configured integrations.",
    response_description="Current service health status with dependency diagnostics.",
)
def health_check(
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    report, healthy = get_health_report(db)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
