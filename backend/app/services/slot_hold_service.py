from datetime import datetime, timedelta, timezone
import secrets
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.channel import TestDriveSlotHold
from app.models.workspace import TestDriveSlot
from app.repositories import test_drive_repository


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_active_holds_count_for_slot(db: Session, slot_id: int) -> int:
    """Returns the number of active, unexpired holds on a slot."""
    now = datetime.now(timezone.utc)
    return (
        db.query(TestDriveSlotHold)
        .filter(
            TestDriveSlotHold.slot_id == slot_id,
            TestDriveSlotHold.status == "held",
            TestDriveSlotHold.expires_at > now,
        )
        .count()
    )


def acquire_slot_hold(
    db: Session,
    dealership_id: int,
    slot_id: int,
    identifier: str,
    customer_id: int | None = None,
    duration_minutes: int = 10,
) -> TestDriveSlotHold:
    """
    Atomically places a temporary hold on a test-drive slot with TTL.
    Prevents race conditions / double bookings while waiting for customer OTP verification.
    """
    now = datetime.now(timezone.utc)

    # 1. Clean up any expired holds on this slot
    expired_holds = (
        db.query(TestDriveSlotHold)
        .filter(
            TestDriveSlotHold.slot_id == slot_id,
            TestDriveSlotHold.status == "held",
            TestDriveSlotHold.expires_at <= now,
        )
        .all()
    )
    for hold in expired_holds:
        hold.status = "expired"

    # 2. Lock the slot with SELECT ... FOR UPDATE
    slot = (
        db.query(TestDriveSlot)
        .filter(
            TestDriveSlot.id == slot_id,
            TestDriveSlot.dealership_id == dealership_id,
        )
        .with_for_update()
        .first()
    )

    if slot is None:
        raise NotFoundError("Test-drive slot not found")

    if not slot.is_active:
        raise ConflictError("Test-drive slot is inactive")

    slot_starts_utc = slot.starts_at if slot.starts_at.tzinfo else slot.starts_at.replace(tzinfo=timezone.utc)
    if slot_starts_utc <= now:
        raise ConflictError("Test-drive slot is in the past")

    # 3. Check combined capacity: booked + active holds
    active_holds_count = (
        db.query(TestDriveSlotHold)
        .filter(
            TestDriveSlotHold.slot_id == slot.id,
            TestDriveSlotHold.status == "held",
            TestDriveSlotHold.expires_at > now,
        )
        .count()
    )

    if (slot.booked_count + active_holds_count) >= slot.capacity:
        raise ConflictError("No remaining capacity available for this slot (currently reserved or booked)")

    # 4. Create the new hold
    hold_token = f"hold_{secrets.token_hex(20)}"
    new_hold = TestDriveSlotHold(
        dealership_id=dealership_id,
        slot_id=slot.id,
        customer_id=customer_id,
        identifier=identifier.strip().lower(),
        hold_token=hold_token,
        status="held",
        expires_at=now + timedelta(minutes=duration_minutes),
        created_at=now,
    )
    db.add(new_hold)
    db.commit()
    db.refresh(new_hold)
    return new_hold


def release_slot_hold(db: Session, hold_token: str) -> None:
    """Manually releases a held slot reservation."""
    hold = (
        db.query(TestDriveSlotHold)
        .filter(TestDriveSlotHold.hold_token == hold_token)
        .first()
    )
    if hold is not None and hold.status == "held":
        hold.status = "released"
        db.commit()


def get_active_slot_hold(db: Session, hold_token: str) -> TestDriveSlotHold | None:
    """Returns the hold record if active, unexpired, and valid."""
    now = datetime.now(timezone.utc)
    hold = (
        db.query(TestDriveSlotHold)
        .filter(TestDriveSlotHold.hold_token == hold_token)
        .first()
    )
    if hold is None or hold.status != "held" or _utc(hold.expires_at) <= now:
        return None
    return hold


def confirm_slot_hold(db: Session, hold_token: str) -> TestDriveSlotHold:
    """Marks a hold confirmed once the final booking is created."""
    hold = (
        db.query(TestDriveSlotHold)
        .filter(TestDriveSlotHold.hold_token == hold_token)
        .first()
    )
    if hold is None:
        raise NotFoundError("Reservation hold not found")

    now = datetime.now(timezone.utc)
    if hold.status != "held" or _utc(hold.expires_at) <= now:
        raise ConflictError("Reservation hold has expired or was already used")

    hold.status = "confirmed"
    db.commit()
    db.refresh(hold)
    return hold
