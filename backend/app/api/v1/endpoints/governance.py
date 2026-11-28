from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.core.errors import BadRequestError
from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.services import outbox_service, reporting_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}",
    tags=["Reporting & Outbox"],
)


class OutboxEventOut(BaseModel):
    id: int
    dealership_id: int
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    target_webhook_url: str | None = None
    status: str
    attempts: int
    last_error: str | None = None
    next_retry_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/reports/summary")
def get_dealership_report_summary(
    dealership_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cache_key = f"dealerdesk:reports:summary:{dealership_id}"
    cached = redis_client.get_json(cache_key)
    if isinstance(cached, dict):
        return cached
    summary = reporting_service.get_dealership_report_summary(db, dealership_id)
    redis_client.set_json(cache_key, summary, ttl_seconds=20)
    return summary


@router.get("/reports/analytics")
def get_dealership_report_analytics(
    dealership_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    resolved_end = end_date or today
    resolved_start = start_date or (resolved_end - timedelta(days=29))
    if resolved_start > resolved_end:
        raise BadRequestError("start_date must be on or before end_date")
    return reporting_service.get_dealership_report_analytics(
        db,
        dealership_id,
        resolved_start,
        resolved_end,
    )


@router.get("/outbox", response_model=list[OutboxEventOut])
def list_outbox_events(
    dealership_id: int,
    event_status: Literal["pending", "delivered", "failed"] | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> list[OutboxEventOut]:
    items = outbox_service.list_outbox_events(
        db,
        dealership_id,
        status=event_status,
        limit=limit,
        offset=offset,
    )
    return [OutboxEventOut.model_validate(item) for item in items]


@router.post("/outbox/dispatch")
def dispatch_outbox_events(
    dealership_id: int,
    default_webhook_url: str | None = Query(default=None),
    dry_run: bool = Query(default=False),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return outbox_service.dispatch_pending_outbox_events(
        db,
        dealership_id=dealership_id,
        default_webhook_url=default_webhook_url,
        dry_run=dry_run,
    )
