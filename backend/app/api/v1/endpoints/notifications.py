from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_role_access
from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.channel import Conversation
from app.models.user import User
from app.models.workspace import CustomerLead, TestDriveBooking, TestDriveSlot
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


class InAppNotificationOut(BaseModel):
    id: str
    title: str
    message: str
    href: str
    severity: str
    created_at: datetime


@router.get("/center", response_model=list[InAppNotificationOut])
def list_in_app_notifications(
    dealership_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[InAppNotificationOut]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    now = datetime.now(timezone.utc)
    items: list[InAppNotificationOut] = []

    overdue_query = select(CustomerLead).where(
        CustomerLead.dealership_id == dealership_id,
        CustomerLead.next_follow_up_at.is_not(None),
        CustomerLead.next_follow_up_at <= now,
        CustomerLead.status.notin_(["won", "lost"]),
    )
    if current_user.role == "sales_rep":
        overdue_query = overdue_query.where(
            or_(
                CustomerLead.assigned_to_user_id == current_user.id,
                CustomerLead.assigned_to_user_id.is_(None),
            )
        )
    for lead in db.scalars(
        overdue_query.order_by(CustomerLead.next_follow_up_at).limit(10)
    ):
        items.append(
            InAppNotificationOut(
                id=f"lead-overdue-{lead.id}",
                title="Overdue lead follow-up",
                message=f"{lead.name} · {lead.next_follow_up_at.isoformat()}",
                href="/leads",
                severity="urgent",
                created_at=lead.next_follow_up_at,
            )
        )

    handoff_query = select(Conversation).where(
        Conversation.dealership_id == dealership_id,
        Conversation.status == "handed_off",
    )
    if current_user.role == "sales_rep":
        handoff_query = handoff_query.where(
            Conversation.channel_metadata["assigned_to_user_id"].as_string()
            == str(current_user.id)
        )
    handoffs = db.scalars(
        handoff_query.order_by(Conversation.updated_at.desc()).limit(10)
    )
    for conversation in handoffs:
        items.append(
            InAppNotificationOut(
                id=f"handoff-{conversation.id}",
                title="Conversation needs attention",
                message=f"{conversation.channel.title()} · {conversation.channel_user_id}",
                href="/inbox",
                severity="high",
                created_at=conversation.updated_at,
            )
        )

    upcoming = select(TestDriveBooking, TestDriveSlot).join(
        TestDriveSlot, TestDriveSlot.id == TestDriveBooking.slot_id
    ).where(
        TestDriveBooking.dealership_id == dealership_id,
        TestDriveBooking.status == "booked",
        TestDriveSlot.starts_at >= now,
        TestDriveSlot.starts_at <= now + timedelta(hours=24),
    )
    if current_user.role == "sales_rep":
        upcoming = upcoming.where(
            TestDriveBooking.assigned_to_user_id == current_user.id
        )
    for booking, slot in db.execute(
        upcoming.order_by(TestDriveSlot.starts_at).limit(10)
    ):
        items.append(
            InAppNotificationOut(
                id=f"booking-upcoming-{booking.id}",
                title="Upcoming test drive",
                message=f"Booking #{booking.id} · {slot.starts_at.isoformat()}",
                href="/bookings",
                severity="normal",
                created_at=slot.starts_at,
            )
        )

    return sorted(items, key=lambda item: item.created_at, reverse=True)[:20]


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
