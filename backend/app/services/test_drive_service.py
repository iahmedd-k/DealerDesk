from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_access, ensure_role
from app.core.errors import (
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.roles import (
    CUSTOMER_ROLE,
    DEALERSHIP_ADMIN_ROLE,
)
from app.models.user import User
from app.models.workspace import (
    TestDriveBooking,
    TestDriveSettings,
    TestDriveSlot,
)
from app.repositories import dealership_repository, test_drive_repository
from app.schemas.workspace import (
    TestDriveSettingsRequest,
    TestDriveSlotUpdateRequest,
)


def get_settings(db: Session, dealership_id: int) -> TestDriveSettings:
    _get_active_dealership(db, dealership_id)
    settings = test_drive_repository.get_settings(db, dealership_id)
    if settings is None:
        raise NotFoundError("Test-drive settings not found")
    return settings


def update_settings(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: TestDriveSettingsRequest,
) -> TestDriveSettings:
    _ensure_admin_access(current_user, dealership_id)
    dealership = _get_active_dealership(db, dealership_id)
    opening = _parse_time(payload.opening_time)
    closing = _parse_time(payload.closing_time)
    if opening >= closing:
        raise UnprocessableEntityError("Opening time must be before closing time")
    settings = test_drive_repository.get_settings(db, dealership_id)
    if settings is None:
        settings = TestDriveSettings(dealership_id=dealership_id)
    settings.opening_time = payload.opening_time
    settings.closing_time = payload.closing_time
    settings.slot_duration_minutes = payload.slot_duration_minutes
    settings.capacity_per_slot = payload.capacity_per_slot
    settings.days_open = ",".join(str(day) for day in payload.days_open)
    _reconcile_future_slots(db, dealership_id, settings, ZoneInfo(dealership.timezone))
    return test_drive_repository.save_settings(db, settings)


def generate_slots(
    db: Session,
    dealership_id: int,
    current_user: User,
    start_date: date,
    end_date: date,
) -> list[TestDriveSlot]:
    _ensure_admin_access(current_user, dealership_id)
    if end_date < start_date or (end_date - start_date).days > 90:
        raise UnprocessableEntityError("Date range must be 0 to 90 days")
    dealership = _get_active_dealership(db, dealership_id)
    settings = test_drive_repository.get_settings(db, dealership_id)
    if settings is None:
        raise UnprocessableEntityError("Configure test-drive settings first")
    vehicles = test_drive_repository.list_eligible_vehicles(db, dealership_id)
    opening = _parse_time(settings.opening_time)
    closing = _parse_time(settings.closing_time)
    zone = ZoneInfo(dealership.timezone)
    open_days = {int(day) for day in settings.days_open.split(",") if day}
    created: list[TestDriveSlot] = []
    current_day = start_date
    while current_day <= end_date:
        if current_day.weekday() in open_days:
            for slot_start, slot_end in _slots_for_day(
                current_day,
                opening,
                closing,
                settings.slot_duration_minutes,
                zone,
            ):
                for vehicle in vehicles:
                    exists = test_drive_repository.get_slot_for_vehicle_start(
                        db,
                        dealership_id,
                        vehicle.id,
                        slot_start,
                    )
                    if exists is None:
                        created.append(
                            TestDriveSlot(
                                dealership_id=dealership_id,
                                vehicle_id=vehicle.id,
                                starts_at=slot_start,
                                ends_at=slot_end,
                                capacity=settings.capacity_per_slot,
                            )
                        )
        current_day += timedelta(days=1)
    return test_drive_repository.save_generated_slots(db, created)


def delete_settings(
    db: Session,
    dealership_id: int,
    current_user: User,
) -> None:
    _ensure_admin_access(current_user, dealership_id)
    settings = test_drive_repository.get_settings(db, dealership_id)
    if settings is None:
        raise NotFoundError("Test-drive settings not found")
    test_drive_repository.delete_settings_and_deactivate_future_slots(
        db,
        settings,
        dealership_id,
        datetime.now(timezone.utc),
    )


def list_slots(
    db: Session,
    dealership_id: int,
    *,
    include_inactive: bool = False,
) -> list[TestDriveSlot]:
    _get_active_dealership(db, dealership_id)
    return test_drive_repository.list_slots(
        db,
        dealership_id,
        include_inactive=include_inactive,
    )


def get_slot(db: Session, dealership_id: int, slot_id: int) -> TestDriveSlot:
    _get_active_dealership(db, dealership_id)
    return _get_slot(db, dealership_id, slot_id)


def update_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    current_user: User,
    payload: TestDriveSlotUpdateRequest,
) -> TestDriveSlot:
    _ensure_admin_access(current_user, dealership_id)
    slot = _get_slot(db, dealership_id, slot_id, lock=True)
    if not payload.is_active and slot.booked_count:
        raise ConflictError("Booked slots cannot be disabled")
    slot.is_active = payload.is_active
    test_drive_repository.save(db, slot)
    return slot


def delete_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    current_user: User,
) -> None:
    _ensure_admin_access(current_user, dealership_id)
    slot = _get_slot(db, dealership_id, slot_id, lock=True)
    if slot.booked_count:
        raise ConflictError("Booked slots cannot be disabled")
    slot.is_active = False
    test_drive_repository.save(db, slot)


def list_bookings_for_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    current_user: User,
) -> list[TestDriveBooking]:
    slot = _get_slot(db, dealership_id, slot_id)
    if current_user.role == CUSTOMER_ROLE:
        customer_id = current_user.id
    else:
        ensure_dealership_access(current_user, dealership_id)
        customer_id = None
    return test_drive_repository.list_bookings_for_slot(
        db,
        dealership_id,
        slot.id,
        customer_id=customer_id,
    )


def list_customer_bookings(
    db: Session,
    dealership_id: int,
    current_user: User,
) -> list[TestDriveBooking]:
    ensure_role(current_user, CUSTOMER_ROLE)
    return test_drive_repository.list_customer_bookings(
        db,
        dealership_id,
        current_user.id,
    )


def book_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    current_user: User,
) -> TestDriveBooking:
    ensure_role(current_user, CUSTOMER_ROLE)
    _get_active_dealership(db, dealership_id)
    slot = _get_slot(db, dealership_id, slot_id, lock=True)
    if not slot.is_active:
        raise ConflictError("Test-drive slot is inactive")
    if _utc(slot.starts_at) <= datetime.now(timezone.utc):
        raise ConflictError("Test-drive slot is in the past")
    if slot.booked_count >= slot.capacity:
        raise ConflictError("Test-drive slot is full")
    vehicle = test_drive_repository.get_vehicle(db, slot.vehicle_id)
    brand = (
        test_drive_repository.get_brand(db, vehicle.brand_id)
        if vehicle is not None
        else None
    )
    if (
        vehicle is None
        or not vehicle.is_available
        or not vehicle.test_drive_enabled
        or brand is None
        or not brand.is_active
        or brand.is_deleted
    ):
        raise ConflictError("Vehicle is unavailable for test drives")
    if test_drive_repository.has_booking(db, slot.id, current_user.id):
        raise ConflictError("Customer already booked this slot")
    booking = TestDriveBooking(
        slot_id=slot.id,
        dealership_id=dealership_id,
        vehicle_id=vehicle.id,
        customer_id=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    try:
        return test_drive_repository.create_booking(db, booking, slot)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Customer already booked this slot") from exc


def cancel_booking(
    db: Session,
    dealership_id: int,
    booking_id: int,
    current_user: User,
) -> None:
    booking = test_drive_repository.get_booking(
        db,
        dealership_id,
        booking_id,
        lock=True,
    )
    if booking is None:
        raise NotFoundError("Booking not found")
    if current_user.role == CUSTOMER_ROLE:
        if booking.customer_id != current_user.id:
            raise NotFoundError("Booking not found")
    else:
        ensure_dealership_access(current_user, dealership_id)
    if booking.status == "booked":
        booking.status = "cancelled"
        booking.cancelled_at = datetime.now(timezone.utc)
        slot = test_drive_repository.get_slot_by_id(db, booking.slot_id, lock=True)
        if slot is not None and slot.booked_count > 0:
            slot.booked_count -= 1
        if slot is None:
            test_drive_repository.save(db, booking)
        else:
            test_drive_repository.save(db, booking, slot)


def _ensure_admin_access(current_user: User, dealership_id: int) -> None:
    ensure_dealership_access(current_user, dealership_id)
    ensure_role(current_user, DEALERSHIP_ADMIN_ROLE)


def _get_active_dealership(db: Session, dealership_id: int):
    dealership = dealership_repository.get_active_by_id(db, dealership_id)
    if dealership is None:
        raise NotFoundError("Dealership not found")
    return dealership


def _get_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    *,
    lock: bool = False,
) -> TestDriveSlot:
    slot = test_drive_repository.get_slot(
        db,
        dealership_id,
        slot_id,
        lock=lock,
    )
    if slot is None:
        raise NotFoundError("Test-drive slot not found")
    return slot


def _slots_for_day(
    current_day: date,
    opening: time,
    closing: time,
    duration_minutes: int,
    zone: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    slots: list[tuple[datetime, datetime]] = []
    slot_start = datetime.combine(current_day, opening)
    closing_at = datetime.combine(current_day, closing)
    duration = timedelta(minutes=duration_minutes)
    while slot_start + duration <= closing_at:
        local_start = _localize(slot_start, zone)
        local_end = _localize(slot_start + duration, zone)
        if local_start is not None and local_end is not None:
            starts_at = local_start.astimezone(timezone.utc)
            ends_at = local_end.astimezone(timezone.utc)
            if starts_at < ends_at:
                slots.append((starts_at, ends_at))
        slot_start += duration
    return slots


def _localize(value: datetime, zone: ZoneInfo) -> datetime | None:
    localized = value.replace(tzinfo=zone)
    if (
        localized.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        != value
    ):
        return None
    return localized


def _reconcile_future_slots(
    db: Session,
    dealership_id: int,
    settings: TestDriveSettings,
    zone: ZoneInfo,
) -> None:
    now = datetime.now(timezone.utc)
    existing_slots = test_drive_repository.list_future_slots_for_update(
        db,
        dealership_id,
        now,
    )
    if not existing_slots:
        return
    vehicles = test_drive_repository.list_eligible_vehicles(db, dealership_id)
    dates = {_utc(slot.starts_at).astimezone(zone).date() for slot in existing_slots}
    open_days = {int(day) for day in settings.days_open.split(",") if day}
    expected: dict[tuple[int, datetime], datetime] = {}
    for current_day in dates:
        if current_day.weekday() not in open_days:
            continue
        for starts_at, ends_at in _slots_for_day(
            current_day,
            _parse_time(settings.opening_time),
            _parse_time(settings.closing_time),
            settings.slot_duration_minutes,
            zone,
        ):
            for vehicle in vehicles:
                expected[(vehicle.id, starts_at)] = ends_at

    existing_keys: set[tuple[int, datetime]] = set()
    for slot in existing_slots:
        key = (slot.vehicle_id, _utc(slot.starts_at))
        existing_keys.add(key)
        ends_at = expected.get(key)
        if ends_at is None:
            slot.is_active = False
        elif slot.is_active:
            slot.ends_at = ends_at
            slot.capacity = max(slot.booked_count, settings.capacity_per_slot)

    for (vehicle_id, starts_at), ends_at in expected.items():
        if (vehicle_id, starts_at) not in existing_keys:
            test_drive_repository.add_slots(
                db,
                [
                    TestDriveSlot(
                        dealership_id=dealership_id,
                        vehicle_id=vehicle_id,
                        starts_at=starts_at,
                        ends_at=ends_at,
                        capacity=settings.capacity_per_slot,
                    )
                ],
            )


def _parse_time(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour=hour, minute=minute)


def _utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )
