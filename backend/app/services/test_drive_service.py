from datetime import date, datetime, time, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_access, ensure_dealership_role_access, ensure_role
from app.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.roles import (
    CUSTOMER_ROLE,
    DEALERSHIP_ADMIN_ROLE,
    MANAGER_ROLE,
    STAFF_ROLES,
)
from app.models.user import User
from app.models.workspace import (
    CustomerLead,
    LeadActivity,
    TestDriveBooking,
    TestDriveSettings,
    TestDriveSlot,
    Vehicle,
)
from app.repositories import test_drive_repository, user_repository
from app.schemas.workspace import (
    TestDriveBookingRequest,
    TestDriveCancellationRequest,
    TestDriveBookingOutcomeRequest,
    TestDriveRescheduleRequest,
    TestDriveSettingsRequest,
    TestDriveSlotCreateRequest,
    TestDriveSlotUpdateRequest,
)
from app.services import audit_service, dealership_service, email_service, outbox_service

logger = logging.getLogger(__name__)


def get_settings(db: Session, dealership_id: int) -> TestDriveSettings:
    dealership_service.get_active_dealership(db, dealership_id)
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
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)
    dealership = dealership_service.get_active_dealership(db, dealership_id)
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
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)
    if end_date < start_date or (end_date - start_date).days > 90:
        raise UnprocessableEntityError("Date range must be 0 to 90 days")
    dealership = dealership_service.get_active_dealership(db, dealership_id)
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
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)
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
    vehicle_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    available_only: bool = False,
    include_inactive: bool = False,
) -> list[TestDriveSlot]:
    if start_date is not None and end_date is not None and end_date < start_date:
        raise UnprocessableEntityError("End date must be on or after start date")
    dealership = dealership_service.get_active_dealership(db, dealership_id)
    zone = ZoneInfo(dealership.timezone)
    start_at = (
        datetime.combine(start_date, time.min, tzinfo=zone).astimezone(timezone.utc)
        if start_date is not None
        else None
    )
    end_at = (
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(
            timezone.utc
        )
        if end_date is not None
        else None
    )
    return test_drive_repository.list_slots(
        db,
        dealership_id,
        vehicle_id=vehicle_id,
        start_at=start_at,
        end_at=end_at,
        available_only=available_only,
        include_inactive=include_inactive,
    )


def get_slot(db: Session, dealership_id: int, slot_id: int) -> TestDriveSlot:
    dealership_service.get_active_dealership(db, dealership_id)
    return _get_slot(db, dealership_id, slot_id)


def create_slot(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: TestDriveSlotCreateRequest,
) -> TestDriveSlot:
    ensure_dealership_role_access(
        current_user, dealership_id, DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE
    )
    dealership_service.get_active_dealership(db, dealership_id)
    vehicle = db.scalar(
        select(Vehicle).where(
            Vehicle.id == payload.vehicle_id,
            Vehicle.dealership_id == dealership_id,
        )
    )
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    if (
        not vehicle.is_available
        or vehicle.status != "available"
        or not vehicle.test_drive_enabled
    ):
        raise UnprocessableEntityError(
            "Vehicle must be available and test-drive enabled before creating a slot"
        )
    if payload.starts_at <= datetime.now(timezone.utc):
        raise UnprocessableEntityError("Slot start time must be in the future")
    if payload.ends_at <= payload.starts_at:
        raise UnprocessableEntityError("Slot end time must be after start time")
    if payload.ends_at - payload.starts_at > timedelta(hours=8):
        raise UnprocessableEntityError("A test-drive slot cannot be longer than 8 hours")
    existing = test_drive_repository.get_slot_for_vehicle_start(
        db,
        dealership_id,
        payload.vehicle_id,
        payload.starts_at,
    )
    if existing is not None:
        raise ConflictError("A slot already exists for this vehicle at that start time")
    overlapping = test_drive_repository.get_overlapping_slot(
        db,
        dealership_id,
        payload.vehicle_id,
        payload.starts_at,
        payload.ends_at,
    )
    if overlapping is not None:
        raise ConflictError(
            f"This vehicle already has an overlapping slot (slot #{overlapping.id})"
        )
    slot = TestDriveSlot(
        dealership_id=dealership_id,
        vehicle_id=payload.vehicle_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        capacity=payload.capacity,
    )
    test_drive_repository.save(db, slot)
    return slot


def update_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    current_user: User,
    payload: TestDriveSlotUpdateRequest,
) -> TestDriveSlot:
    ensure_dealership_role_access(
        current_user, dealership_id, DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE
    )
    slot = _get_slot(db, dealership_id, slot_id, lock=True)
    if payload.is_active is not None:
        if not payload.is_active and slot.booked_count:
            raise ConflictError("Booked slots cannot be disabled")
        slot.is_active = payload.is_active
    if payload.capacity is not None:
        if payload.capacity < slot.booked_count:
            raise ConflictError("Capacity cannot be less than booked_count")
        slot.capacity = payload.capacity
    test_drive_repository.save(db, slot)
    return slot


def delete_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    current_user: User,
) -> None:
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)
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


def get_booking(
    db: Session,
    dealership_id: int,
    booking_id: int,
    current_user: User,
) -> TestDriveBooking:
    dealership = dealership_service.get_active_dealership(db, dealership_id)
    booking = test_drive_repository.get_booking(db, dealership_id, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found")
    if current_user.role == CUSTOMER_ROLE:
        if booking.customer_id != current_user.id:
            raise NotFoundError("Booking not found")
    else:
        ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    return booking


def list_bookings(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    status: str | None = None,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    slot_id: int | None = None,
) -> list[TestDriveBooking]:
    dealership_service.get_active_dealership(db, dealership_id)
    if current_user.role == CUSTOMER_ROLE:
        return test_drive_repository.list_bookings(
            db,
            dealership_id,
            customer_id=current_user.id,
            status=status,
            vehicle_id=vehicle_id,
            slot_id=slot_id,
        )
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    return test_drive_repository.list_bookings(
        db,
        dealership_id,
        customer_id=customer_id,
        status=status,
        vehicle_id=vehicle_id,
        slot_id=slot_id,
    )


def update_booking_outcome(
    db: Session,
    dealership_id: int,
    booking_id: int,
    current_user: User,
    payload: TestDriveBookingOutcomeRequest,
) -> TestDriveBooking:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    if not payload.model_fields_set:
        raise UnprocessableEntityError("At least one booking field is required")
    booking = test_drive_repository.get_booking(
        db, dealership_id, booking_id, lock=True
    )
    if booking is None:
        raise NotFoundError("Booking not found")

    changes = payload.model_dump(exclude_unset=True)
    if "assigned_to_user_id" in changes and booking.status != "booked":
        raise ConflictError("Only booked test drives can be assigned a host")
    if "assigned_to_user_id" in changes and changes["assigned_to_user_id"] is not None:
        host = db.scalar(
            select(User).where(
                User.id == changes["assigned_to_user_id"],
                User.dealership_id == dealership_id,
                User.role.in_(STAFF_ROLES),
                User.is_active.is_(True),
            )
        )
        if host is None:
            raise NotFoundError("Active dealership staff member not found")
        booking.assigned_to_user_id = host.id
    elif "assigned_to_user_id" in changes:
        booking.assigned_to_user_id = None

    outcome = changes.get("status")
    if outcome is not None:
        if booking.status != "booked":
            raise ConflictError("Only booked test drives can receive an outcome")
        booking.status = outcome
        booking.outcome_at = datetime.now(timezone.utc)
        _sync_lead_after_booking_change(
            db,
            booking,
            status="qualified" if outcome == "completed" else "follow_up",
            follow_up_at=(
                None
                if outcome == "completed"
                else datetime.now(timezone.utc) + timedelta(hours=1)
            ),
            summary=(
                "Test drive completed"
                if outcome == "completed"
                else "Customer missed test drive; follow-up required"
            ),
        )
    if "outcome_notes" in changes:
        booking.outcome_notes = changes["outcome_notes"]

    test_drive_repository.save(db, booking)
    audit_service.log_event(
        db,
        action="booking.updated",
        resource_type="test_drive_booking",
        resource_id=str(booking.id),
        dealership_id=dealership_id,
        actor=current_user,
        details=changes,
    )
    return booking


def list_customer_bookings(
    db: Session,
    dealership_id: int,
    current_user: User,
) -> list[TestDriveBooking]:
    return list_bookings(db, dealership_id, current_user)


def book_slot(
    db: Session,
    dealership_id: int,
    slot_id: int,
    current_user: User,
    payload: TestDriveBookingRequest,
) -> TestDriveBooking:
    ensure_role(current_user, CUSTOMER_ROLE)
    if not payload.confirmed:
        raise BadRequestError(
            "Explicit confirmation is required to book a test drive"
        )
    dealership = dealership_service.get_active_dealership(db, dealership_id)
    slot = _get_slot(db, dealership_id, slot_id, lock=True)
    if not slot.is_active:
        raise ConflictError("Test-drive slot is inactive")
    if _utc(slot.starts_at) <= datetime.now(timezone.utc):
        raise ConflictError("Test-drive slot is in the past")
    if slot.booked_count >= slot.capacity:
        raise ConflictError("Test-drive slot is full")
    from app.services import slot_hold_service
    if payload.hold_token:
        slot_hold_service.confirm_slot_hold(db, payload.hold_token)
    else:
        active_holds = slot_hold_service.get_active_holds_count_for_slot(db, slot.id)
        if (slot.booked_count + active_holds) >= slot.capacity:
            raise ConflictError("Test-drive slot is currently reserved")
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
    test_drive_repository.lock_customer(db, current_user.id)
    if test_drive_repository.has_booking(db, slot.id, current_user.id):
        raise ConflictError("Customer already booked this slot")
    if test_drive_repository.has_overlapping_booking(
        db, current_user.id, slot.starts_at, slot.ends_at, exclude_slot_id=slot.id
    ):
        raise ConflictError("Customer already has an active test drive during this time")
    booking = TestDriveBooking(
        slot_id=slot.id,
        dealership_id=dealership_id,
        vehicle_id=vehicle.id,
        customer_id=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    try:
        saved_booking = test_drive_repository.create_booking(db, booking, slot)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Customer already booked this slot") from exc

    try:
        zone = ZoneInfo(dealership.timezone)
        email_service.send_test_drive_confirmation(
            recipient=current_user.email,
            customer_name=current_user.name,
            dealership_name=dealership.name,
            dealership_address=dealership.address,
            dealership_phone=dealership.phone,
            vehicle_label=f"{vehicle.model_year} {vehicle.make} {vehicle.model}",
            stock_number=vehicle.stock_number,
            starts_at_local=_format_local_dt(slot.starts_at, zone),
            ends_at_local=_format_local_time(slot.ends_at, zone),
            timezone_name=dealership.timezone,
            booking_id=saved_booking.id,
        )
    except Exception as exc:
        logger.warning("Test-drive confirmation email failed for booking %s: %s", saved_booking.id, exc)
    _sync_lead_for_booking(db, dealership_id, saved_booking, vehicle, current_user)
    try:
        audit_service.log_event(
            db,
            action="booking.created",
            resource_type="test_drive_booking",
            resource_id=str(saved_booking.id),
            dealership_id=dealership_id,
            actor=current_user,
            details={"slot_id": slot.id, "vehicle_id": vehicle.id},
        )
        outbox_service.enqueue_event(
            db,
            dealership_id=dealership_id,
            event_type="booking.confirmed",
            aggregate_type="test_drive_booking",
            aggregate_id=saved_booking.id,
            payload={"booking_id": saved_booking.id, "vehicle_id": vehicle.id, "slot_id": slot.id},
        )
    except Exception as exc:
        logger.warning("Audit/outbox failed for booking %s: %s", saved_booking.id, exc)
    return saved_booking


def reschedule_booking(
    db: Session,
    dealership_id: int,
    booking_id: int,
    payload: TestDriveRescheduleRequest,
    current_user: User,
) -> TestDriveBooking:
    if not payload.confirmed:
        raise BadRequestError(
            "Explicit confirmation is required to reschedule a test drive"
        )
    dealership = dealership_service.get_active_dealership(db, dealership_id)
    booking = test_drive_repository.get_booking(
        db, dealership_id, booking_id, lock=True
    )
    if booking is None:
        raise NotFoundError("Booking not found")
    if current_user.role == CUSTOMER_ROLE:
        if booking.customer_id != current_user.id:
            raise NotFoundError("Booking not found")
        if payload.verification_email is not None:
            if (
                payload.verification_email.strip().lower()
                != current_user.email.strip().lower()
            ):
                raise BadRequestError(
                    "Customer contact verification failed: provided email does not match booking record"
                )
    else:
        ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)

    if booking.status != "booked":
        raise ConflictError(
            f"Cannot reschedule a booking with status '{booking.status}'"
        )

    if payload.new_slot_id == booking.slot_id:
        return booking

    new_slot = _get_slot(db, dealership_id, payload.new_slot_id, lock=True)
    if not new_slot.is_active:
        raise ConflictError("Target test-drive slot is inactive")
    if _utc(new_slot.starts_at) <= datetime.now(timezone.utc):
        raise ConflictError("Target test-drive slot is in the past")
    if new_slot.booked_count >= new_slot.capacity:
        raise ConflictError("Target test-drive slot is full")

    vehicle = test_drive_repository.get_vehicle(db, new_slot.vehicle_id)
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
        raise ConflictError("Target vehicle is unavailable for test drives")

    test_drive_repository.lock_customer(db, booking.customer_id)
    if test_drive_repository.has_booking(db, new_slot.id, booking.customer_id):
        raise ConflictError("Customer already booked the target slot")
    if test_drive_repository.has_overlapping_booking(
        db,
        booking.customer_id,
        new_slot.starts_at,
        new_slot.ends_at,
        exclude_slot_id=booking.slot_id,
    ):
        raise ConflictError(
            "Customer already has an active test drive during target time"
        )

    old_slot = test_drive_repository.get_slot_by_id(db, booking.slot_id, lock=True)
    if old_slot is not None and old_slot.booked_count > 0:
        old_slot.booked_count -= 1

    new_slot.booked_count += 1
    booking.slot_id = new_slot.id
    booking.vehicle_id = new_slot.vehicle_id
    _sync_lead_after_booking_change(
        db,
        booking,
        status="test_drive_scheduled",
        follow_up_at=None,
        summary="Test drive rescheduled",
        vehicle_id=new_slot.vehicle_id,
    )

    if old_slot is not None:
        test_drive_repository.save(db, booking, old_slot, new_slot)
    else:
        test_drive_repository.save(db, booking, new_slot)

    try:
        customer = user_repository.get_by_id(db, booking.customer_id)
        if customer is not None:
            zone = ZoneInfo(dealership.timezone)
            email_service.send_test_drive_rescheduled(
                recipient=customer.email,
                customer_name=customer.name,
                dealership_name=dealership.name,
                dealership_address=dealership.address,
                vehicle_label=f"{vehicle.model_year} {vehicle.make} {vehicle.model}",
                starts_at_local=_format_local_dt(new_slot.starts_at, zone),
                ends_at_local=_format_local_time(new_slot.ends_at, zone),
                timezone_name=dealership.timezone,
                booking_id=booking.id,
            )
    except Exception as exc:
        logger.warning("Test-drive reschedule email failed for booking %s: %s", booking.id, exc)
    return booking


def cancel_booking(
    db: Session,
    dealership_id: int,
    booking_id: int,
    current_user: User,
    payload: TestDriveCancellationRequest | None = None,
    verification_email: str | None = None,
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
        check_email = verification_email or (
            payload.verification_email if payload else None
        )
        if check_email is not None:
            if check_email.strip().lower() != current_user.email.strip().lower():
                raise BadRequestError(
                    "Customer contact verification failed: provided email does not match booking record"
                )
    else:
        ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    if booking.status == "booked":
        now = datetime.now(timezone.utc)
        booking.status = "cancelled"
        booking.cancelled_at = now
        if payload and payload.reason:
            booking.outcome_notes = payload.reason.strip()
        slot = test_drive_repository.get_slot_by_id(db, booking.slot_id, lock=True)
        if slot is not None and slot.booked_count > 0:
            slot.booked_count -= 1
        _sync_lead_after_booking_change(
            db,
            booking,
            status="follow_up",
            follow_up_at=now + timedelta(hours=1),
            summary="Test drive cancelled; customer follow-up required",
        )
        if slot is None:
            test_drive_repository.save(db, booking)
        else:
            test_drive_repository.save(db, booking, slot)

        try:
            dealership = dealership_service.get_active_dealership(db, dealership_id)
            customer = user_repository.get_by_id(db, booking.customer_id)
            vehicle = test_drive_repository.get_vehicle(db, booking.vehicle_id)
            if customer is not None and slot is not None and vehicle is not None:
                zone = ZoneInfo(dealership.timezone)
                email_service.send_test_drive_cancelled(
                    recipient=customer.email,
                    customer_name=customer.name,
                    dealership_name=dealership.name,
                    vehicle_label=f"{vehicle.model_year} {vehicle.make} {vehicle.model}",
                    starts_at_local=_format_local_dt(slot.starts_at, zone),
                    timezone_name=dealership.timezone,
                    booking_id=booking.id,
                )
        except Exception as exc:
            logger.warning("Test-drive cancellation email failed for booking %s: %s", booking.id, exc)


def _sync_lead_after_booking_change(
    db: Session,
    booking: TestDriveBooking,
    *,
    status: str,
    follow_up_at: datetime | None,
    summary: str,
    vehicle_id: int | None = None,
) -> None:
    lead = db.scalar(
        select(CustomerLead).where(
            CustomerLead.dealership_id == booking.dealership_id,
            CustomerLead.test_drive_booking_id == booking.id,
        )
    )
    if lead is None or lead.status in {"won", "lost"}:
        return

    now = datetime.now(timezone.utc)
    previous_status = lead.status
    if lead.status == "test_drive_scheduled":
        lead.status = status
    if vehicle_id is not None:
        lead.requested_vehicle_id = vehicle_id
    lead.next_follow_up_at = follow_up_at
    lead.updated_at = now
    db.add(
        LeadActivity(
            dealership_id=booking.dealership_id,
            lead_id=lead.id,
            actor_user_id=None,
            activity_type="booking_updated",
            summary=summary,
            details={
            "booking_id": booking.id,
            "previous_lead_status": previous_status,
            "lead_status": lead.status,
            "vehicle_id": vehicle_id or booking.vehicle_id,
            },
            created_at=now,
        )
    )
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


def _format_local_dt(value: datetime, zone: ZoneInfo) -> str:
    return _utc(value).astimezone(zone).strftime("%b %d, %Y at %I:%M %p")


def _format_local_time(value: datetime, zone: ZoneInfo) -> str:
    return _utc(value).astimezone(zone).strftime("%I:%M %p")


def _sync_lead_for_booking(
    db: Session,
    dealership_id: int,
    booking: TestDriveBooking,
    vehicle: Vehicle,
    customer: User,
) -> None:
    """
    Auto-link an existing open CRM lead for this customer & dealership, or create a
    new CRM lead in 'test_drive_scheduled' status so staff can convert it to won/lost.
    """
    try:
        now = datetime.now(timezone.utc)
        existing_lead = db.scalar(
            select(CustomerLead)
            .where(
                CustomerLead.dealership_id == dealership_id,
                CustomerLead.email.ilike(customer.email),
                CustomerLead.test_drive_booking_id.is_(None),
                CustomerLead.status.notin_(["won", "lost"]),
            )
            .order_by(CustomerLead.created_at.desc())
        )
        if existing_lead is not None:
            existing_lead.test_drive_booking_id = booking.id
            existing_lead.status = "test_drive_scheduled"
            existing_lead.customer_id = customer.id
            if existing_lead.requested_vehicle_id is None:
                existing_lead.requested_vehicle_id = vehicle.id
            existing_lead.next_follow_up_at = None
            existing_lead.updated_at = now
            db.commit()
            return

        new_lead = CustomerLead(
            dealership_id=dealership_id,
            customer_id=customer.id,
            requested_vehicle_id=vehicle.id,
            test_drive_booking_id=booking.id,
            name=customer.name,
            email=customer.email.lower(),
            message=(
                f"Booked test drive for {vehicle.model_year} {vehicle.make} {vehicle.model} "
                f"(Stock #{vehicle.stock_number})."
            ),
            source="test_drive",
            status="test_drive_scheduled",
            consent_to_contact=True,
            consented_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(new_lead)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to auto-sync CRM lead for booking %s: %s", booking.id, exc)
