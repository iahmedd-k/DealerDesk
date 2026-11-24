from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import (
    Brand,
    TestDriveBooking,
    TestDriveSettings,
    TestDriveSlot,
    Vehicle,
)


def get_settings(db: Session, dealership_id: int) -> TestDriveSettings | None:
    return db.scalar(
        select(TestDriveSettings).where(
            TestDriveSettings.dealership_id == dealership_id
        )
    )


def save_settings(db: Session, settings: TestDriveSettings) -> TestDriveSettings:
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def list_eligible_vehicles(db: Session, dealership_id: int) -> list[Vehicle]:
    return list(
        db.scalars(
            select(Vehicle).where(
                Vehicle.dealership_id == dealership_id,
                Vehicle.is_available.is_(True),
                Vehicle.test_drive_enabled.is_(True),
                Vehicle.brand_id.in_(
                    select(Brand.id).where(
                        Brand.is_active.is_(True),
                        Brand.is_deleted.is_(False),
                    )
                ),
            )
        )
    )


def list_slots(
    db: Session,
    dealership_id: int,
    *,
    vehicle_id: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    available_only: bool = False,
    include_inactive: bool = False,
) -> list[TestDriveSlot]:
    query = select(TestDriveSlot).where(
        TestDriveSlot.dealership_id == dealership_id
    )
    if not include_inactive:
        query = query.where(TestDriveSlot.is_active.is_(True))
    if vehicle_id is not None:
        query = query.where(TestDriveSlot.vehicle_id == vehicle_id)
    if start_at is not None:
        query = query.where(TestDriveSlot.starts_at >= start_at)
    if end_at is not None:
        query = query.where(TestDriveSlot.starts_at < end_at)
    if available_only:
        now = datetime.now(timezone.utc)
        query = query.where(
            TestDriveSlot.booked_count < TestDriveSlot.capacity,
            TestDriveSlot.starts_at > now,
            TestDriveSlot.is_active.is_(True),
        )
    return list(db.scalars(query.order_by(TestDriveSlot.starts_at)))


def get_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    *,
    lock: bool = False,
) -> TestDriveSlot | None:
    query = select(TestDriveSlot).where(
        TestDriveSlot.id == slot_id,
        TestDriveSlot.dealership_id == dealership_id,
    )
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def get_slot_by_id(db: Session, slot_id: int, *, lock: bool = False) -> TestDriveSlot | None:
    query = select(TestDriveSlot).where(TestDriveSlot.id == slot_id)
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def get_slot_for_vehicle_start(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    starts_at: datetime,
) -> TestDriveSlot | None:
    return db.scalar(
        select(TestDriveSlot).where(
            TestDriveSlot.dealership_id == dealership_id,
            TestDriveSlot.vehicle_id == vehicle_id,
            TestDriveSlot.starts_at == starts_at,
        )
    )


def list_future_slots_for_update(
    db: Session,
    dealership_id: int,
    now: datetime,
) -> list[TestDriveSlot]:
    return list(
        db.scalars(
            select(TestDriveSlot)
            .where(
                TestDriveSlot.dealership_id == dealership_id,
                TestDriveSlot.starts_at > now,
            )
            .order_by(TestDriveSlot.starts_at)
            .with_for_update()
        )
    )


def add_slots(db: Session, slots: list[TestDriveSlot]) -> None:
    db.add_all(slots)


def save_generated_slots(db: Session, slots: list[TestDriveSlot]) -> list[TestDriveSlot]:
    db.add_all(slots)
    db.commit()
    for slot in slots:
        db.refresh(slot)
    return slots


def list_bookings_for_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    *,
    customer_id: int | None = None,
) -> list[TestDriveBooking]:
    query = select(TestDriveBooking).where(
        TestDriveBooking.dealership_id == dealership_id,
        TestDriveBooking.slot_id == slot_id,
    )
    if customer_id is not None:
        query = query.where(TestDriveBooking.customer_id == customer_id)
    return list(db.scalars(query.order_by(TestDriveBooking.created_at)))


def list_bookings(
    db: Session,
    dealership_id: int,
    *,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    slot_id: int | None = None,
    status: str | None = None,
) -> list[TestDriveBooking]:
    query = select(TestDriveBooking).where(
        TestDriveBooking.dealership_id == dealership_id
    )
    if customer_id is not None:
        query = query.where(TestDriveBooking.customer_id == customer_id)
    if vehicle_id is not None:
        query = query.where(TestDriveBooking.vehicle_id == vehicle_id)
    if slot_id is not None:
        query = query.where(TestDriveBooking.slot_id == slot_id)
    if status is not None:
        query = query.where(TestDriveBooking.status == status)
    return list(db.scalars(query.order_by(TestDriveBooking.created_at.desc())))


def list_customer_bookings(
    db: Session,
    dealership_id: int,
    customer_id: int,
) -> list[TestDriveBooking]:
    return list(
        db.scalars(
            select(TestDriveBooking)
            .where(
                TestDriveBooking.customer_id == customer_id,
                TestDriveBooking.dealership_id == dealership_id,
            )
            .order_by(TestDriveBooking.created_at.desc())
        )
    )


def get_vehicle(db: Session, vehicle_id: int) -> Vehicle | None:
    return db.get(Vehicle, vehicle_id)


def get_brand(db: Session, brand_id: int) -> Brand | None:
    return db.get(Brand, brand_id)


def lock_customer(db: Session, customer_id: int) -> None:
    db.scalar(
        select(User.id)
        .where(User.id == customer_id)
        .with_for_update()
    )


def has_booking(
    db: Session,
    slot_id: int,
    customer_id: int,
) -> bool:
    return (
        db.scalar(
            select(TestDriveBooking.id).where(
                TestDriveBooking.slot_id == slot_id,
                TestDriveBooking.customer_id == customer_id,
                TestDriveBooking.status == "booked",
            )
        )
        is not None
    )


def has_overlapping_booking(
    db: Session,
    customer_id: int,
    starts_at: datetime,
    ends_at: datetime,
    *,
    exclude_slot_id: int | None = None,
) -> bool:
    query = (
        select(TestDriveBooking.id)
        .join(TestDriveSlot, TestDriveBooking.slot_id == TestDriveSlot.id)
        .where(
            TestDriveBooking.customer_id == customer_id,
            TestDriveBooking.status == "booked",
            TestDriveSlot.starts_at < ends_at,
            TestDriveSlot.ends_at > starts_at,
        )
    )
    if exclude_slot_id is not None:
        query = query.where(TestDriveBooking.slot_id != exclude_slot_id)
    return db.scalar(query) is not None


def get_booking(
    db: Session,
    dealership_id: int,
    booking_id: int,
    *,
    lock: bool = False,
) -> TestDriveBooking | None:
    query = select(TestDriveBooking).where(
        TestDriveBooking.id == booking_id,
        TestDriveBooking.dealership_id == dealership_id,
    )
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def create_booking(
    db: Session,
    booking: TestDriveBooking,
    slot: TestDriveSlot,
) -> TestDriveBooking:
    slot.booked_count += 1
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def save(db: Session, *entities: object) -> None:
    db.add_all(entities)
    db.commit()


def delete_settings_and_deactivate_future_slots(
    db: Session,
    settings: TestDriveSettings,
    dealership_id: int,
    now: datetime,
) -> None:
    db.execute(
        TestDriveSlot.__table__.update()
        .where(
            TestDriveSlot.dealership_id == dealership_id,
            TestDriveSlot.starts_at > now,
            TestDriveSlot.is_active.is_(True),
        )
        .values(is_active=False)
    )
    db.delete(settings)
    db.commit()


def commit(db: Session) -> None:
    db.commit()
