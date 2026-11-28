from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import (
    Dealership,
    NotificationDelivery,
    TestDriveBooking,
    TestDriveSlot,
    Vehicle,
)
from app.services import email_service

logger = logging.getLogger("dealerdesk.reminders")

REMINDER_24H = "booking_reminder_24h"
REMINDER_2H = "booking_reminder_2h"
MAX_DELIVERY_ATTEMPTS = 5
INITIAL_RETRY_DELAY = timedelta(minutes=5)


def _utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _map_delivery_status(email_result: str) -> str:
    if email_result == "email_sent":
        return "sent"
    if email_result == "email_provider_pending":
        return "pending"
    if email_result == "email_skipped_synthetic":
        return "skipped_synthetic"
    return "failed"


def process_due_booking_reminders(
    db: Session,
    *,
    dry_run: bool = False,
    dealership_id: int | None = None,
) -> dict[str, Any]:
    """
    Idempotently dispatches 24-hour and 2-hour email reminders for upcoming
    'booked' test drives, recording every delivery attempt in notification_deliveries
    with a unique (booking_id, notification_type) constraint.
    """
    now = datetime.now(timezone.utc)
    window_24h_end = now + timedelta(hours=24)
    window_2h_end = now + timedelta(hours=2)

    query = (
        select(TestDriveBooking, TestDriveSlot, Dealership, Vehicle, User)
        .join(TestDriveSlot, TestDriveSlot.id == TestDriveBooking.slot_id)
        .join(Dealership, Dealership.id == TestDriveBooking.dealership_id)
        .join(Vehicle, Vehicle.id == TestDriveBooking.vehicle_id)
        .join(User, User.id == TestDriveBooking.customer_id)
        .where(
            TestDriveBooking.status == "booked",
            TestDriveSlot.starts_at > now,
            TestDriveSlot.starts_at <= window_24h_end,
            Dealership.is_active.is_(True),
        )
    )
    if dealership_id is not None:
        query = query.where(TestDriveBooking.dealership_id == dealership_id)

    rows = db.execute(query).all()

    stats: dict[str, int] = {
        "evaluated": len(rows),
        "sent_24h": 0,
        "sent_2h": 0,
        "pending": 0,
        "retried": 0,
        "skipped_already_delivered": 0,
        "failed": 0,
    }

    for booking, slot, dealership, vehicle, customer in rows:
        starts_utc = _utc(slot.starts_at)
        if starts_utc <= window_2h_end:
            notif_type = REMINDER_2H
            hours_before = 2
        else:
            notif_type = REMINDER_24H
            hours_before = 24

        existing = db.scalar(
            select(NotificationDelivery).where(
                NotificationDelivery.booking_id == booking.id,
                NotificationDelivery.notification_type == notif_type,
            ).with_for_update(skip_locked=True)
        )
        if existing is not None and existing.status in {"sent", "skipped_synthetic"}:
            stats["skipped_already_delivered"] += 1
            continue
        if existing is not None and (
            existing.attempts >= MAX_DELIVERY_ATTEMPTS
            or (
                existing.next_retry_at is not None
                and _utc(existing.next_retry_at) > now
            )
        ):
            stats["pending" if existing.status in {"pending", "processing"} else "failed"] += 1
            continue

        if dry_run:
            if notif_type == REMINDER_2H:
                stats["sent_2h"] += 1
            else:
                stats["sent_24h"] += 1
            continue

        if existing is None:
            record = NotificationDelivery(
                dealership_id=dealership.id,
                booking_id=booking.id,
                notification_type=notif_type,
                channel="email",
                recipient=customer.email,
                status="processing",
                attempts=1,
                next_retry_at=now + INITIAL_RETRY_DELAY,
                last_attempt_at=now,
                created_at=now,
            )
            db.add(record)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                stats["skipped_already_delivered"] += 1
                continue
            existing = record
        else:
            existing.status = "processing"
            existing.attempts += 1
            existing.last_attempt_at = now
            existing.next_retry_at = now + INITIAL_RETRY_DELAY
            db.commit()
            stats["retried"] += 1

        zone = ZoneInfo(dealership.timezone)
        starts_local = starts_utc.astimezone(zone).strftime("%b %d, %Y at %I:%M %p")
        ends_local = _utc(slot.ends_at).astimezone(zone).strftime("%I:%M %p")
        vehicle_label = f"{vehicle.model_year} {vehicle.make} {vehicle.model}"

        delivery_result = "email_delivery_failed"
        error_msg: str | None = None
        try:
            delivery_result = email_service.send_test_drive_reminder(
                recipient=customer.email,
                customer_name=customer.name,
                dealership_name=dealership.name,
                dealership_address=dealership.address,
                dealership_phone=dealership.phone,
                vehicle_label=vehicle_label,
                stock_number=vehicle.stock_number,
                starts_at_local=starts_local,
                ends_at_local=ends_local,
                timezone_name=dealership.timezone,
                booking_id=booking.id,
                hours_before=hours_before,
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.warning(
                "Reminder email exception for booking %s (%s): %s",
                booking.id,
                notif_type,
                exc,
            )

        ledger_status = _map_delivery_status(delivery_result)
        existing.error_message = error_msg
        existing.last_attempt_at = now
        if ledger_status == "sent":
            existing.status = "sent"
            existing.sent_at = now
            existing.next_retry_at = None
        elif ledger_status == "skipped_synthetic":
            existing.status = "skipped_synthetic"
            existing.next_retry_at = None
        elif existing.attempts < MAX_DELIVERY_ATTEMPTS:
            existing.status = "pending"
            existing.next_retry_at = now + INITIAL_RETRY_DELAY * (2 ** (existing.attempts - 1))
            stats["pending"] += 1
        else:
            existing.status = "failed"
            existing.next_retry_at = None
            stats["failed"] += 1
        db.commit()

        if existing.status == "sent" and notif_type == REMINDER_2H:
            stats["sent_2h"] += 1
        elif existing.status == "sent":
            stats["sent_24h"] += 1

    return {
        "dry_run": dry_run,
        "executed_at": now.isoformat(),
        **stats,
    }


def list_notification_deliveries(
    db: Session,
    dealership_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[NotificationDelivery]:
    return list(
        db.scalars(
            select(NotificationDelivery)
            .where(NotificationDelivery.dealership_id == dealership_id)
            .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
