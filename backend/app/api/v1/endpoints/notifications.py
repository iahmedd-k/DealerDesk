from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.services import reminder_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}/notifications",
    tags=["Notifications & Reminders"],
)


class NotificationDeliveryOut(BaseModel):
    id: int
    dealership_id: int
    booking_id: int | None = None
    notification_type: str
    channel: str
    recipient: str
    status: str
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[NotificationDeliveryOut])
def list_notification_deliveries(
    dealership_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[NotificationDeliveryOut]:
    items = reminder_service.list_notification_deliveries(
        db,
        dealership_id,
        limit=limit,
        offset=offset,
    )
    return [NotificationDeliveryOut.model_validate(item) for item in items]


@router.post("/run-reminders")
def run_due_booking_reminders(
    dealership_id: int,
    dry_run: bool = Query(default=False),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return reminder_service.process_due_booking_reminders(
        db,
        dry_run=dry_run,
        dealership_id=dealership_id,
    )
