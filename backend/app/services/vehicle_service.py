from datetime import datetime, timezone
from decimal import Decimal
import logging
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_access
from app.core.errors import (
    BadGatewayError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.roles import DEALERSHIP_MANAGEMENT_ROLES
from app.models.channel import TestDriveSlotHold
from app.models.user import User
from app.models.workspace import (
    Brand,
    TestDriveBooking,
    TestDriveSlot,
    Vehicle,
    VehicleStatusHistory,
)
from app.repositories import brand_repository, dealership_repository, user_repository, vehicle_repository
from app.schemas.workspace import (
    VehicleCreateRequest,
    VehicleStatusTransitionRequest,
    VehicleUpdateRequest,
)
from app.services import audit_service, dealership_service, email_service, outbox_service

logger = logging.getLogger(__name__)


def decode_vin(vin: str) -> dict[str, str | int | None]:
    normalized_vin = vin.strip().upper()
    if len(normalized_vin) != 17 or any(
        character not in "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
        for character in normalized_vin
    ):
        raise UnprocessableEntityError("VIN must contain 17 valid letters or digits")
    try:
        response = httpx.get(
            "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended",
            params={"format": "json", "vin": normalized_vin},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise BadGatewayError("The VIN decoder service could not be reached.") from exc

    results = payload.get("Results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise BadGatewayError("The VIN decoder returned an invalid response.")
    decoded = results[0]

    def field(name: str) -> str | None:
        value = decoded.get(name)
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip()

    year_value = field("ModelYear")
    try:
        model_year = int(year_value) if year_value else None
    except ValueError:
        model_year = None
    return {
        "vin": normalized_vin,
        "make": field("Make"),
        "model": field("Model"),
        "model_year": model_year,
        "variant": field("Trim"),
        "fuel_type": field("FuelTypePrimary"),
        "drivetrain": field("DriveType"),
        "transmission": field("TransmissionStyle"),
        "body_class": field("BodyClass"),
    }


def create_vehicle(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: VehicleCreateRequest,
) -> Vehicle:
    ensure_dealership_access(current_user, dealership_id)
    dealership = brand_repository.lock_active_dealership(db, dealership_id)
    if dealership is None:
        raise NotFoundError("Dealership not found")
    if vehicle_repository.count_for_dealership(
        db,
        dealership_id,
        include_archived_brands=True,
    ) >= dealership.max_vehicles:
        raise ConflictError("This dealership has reached its vehicle limit")
    brand = _get_active_brand(db, dealership_id, payload.brand_id)
    
    status_val = (payload.status or "available").lower()
    is_available = (status_val == "available")
    payload_data = payload.model_dump(exclude={"brand_id", "status", "acquired_at"})
    
    vehicle = Vehicle(
        dealership_id=dealership_id,
        brand_id=brand.id,
        make=brand.name,
        status=status_val,
        is_available=is_available,
        acquired_at=payload.acquired_at or datetime.now(timezone.utc),
        **payload_data,
    )
    try:
        saved_vehicle = vehicle_repository.save(db, vehicle)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Stock number or VIN already exists in this dealership") from exc

    # Record initial status history
    history = VehicleStatusHistory(
        dealership_id=dealership_id,
        vehicle_id=saved_vehicle.id,
        changed_by_user_id=current_user.id,
        previous_status="none",
        new_status=saved_vehicle.status,
        notes="Initial vehicle creation",
    )
    vehicle_repository.save_status_history(db, history)

    # Log audit event
    audit_service.log_event(
        db,
        action="vehicle.created",
        resource_type="vehicle",
        resource_id=str(saved_vehicle.id),
        dealership_id=dealership_id,
        actor=current_user,
        details={
            "stock_number": saved_vehicle.stock_number,
            "status": saved_vehicle.status,
            "make": saved_vehicle.make,
            "model": saved_vehicle.model,
            "price": float(saved_vehicle.price),
        },
    )
    return saved_vehicle


def list_vehicles(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    include_archived_brands: bool = False,
    brand_id: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    status: str | None = None,
    is_available: bool | None = None,
    test_drive_enabled: bool | None = None,
    fuel_type: str | None = None,
    transmission: str | None = None,
    drivetrain: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    order: str = "asc",
    page: int | None = None,
    page_size: int | None = None,
) -> list[Vehicle]:
    ensure_dealership_access(current_user, dealership_id)
    dealership_service.get_active_dealership(db, dealership_id)
    if (
        include_archived_brands
        and current_user.role not in DEALERSHIP_MANAGEMENT_ROLES
    ):
        raise ForbiddenError("A dealership manager role is required")
    return vehicle_repository.list_for_dealership(
        db,
        dealership_id,
        include_archived_brands=include_archived_brands,
        brand_id=brand_id,
        min_price=min_price,
        max_price=max_price,
        status=status,
        is_available=is_available,
        test_drive_enabled=test_drive_enabled,
        fuel_type=fuel_type,
        transmission=transmission,
        drivetrain=drivetrain,
        search=search,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )


def count_vehicles(
    db: Session,
    dealership_id: int,
    *,
    include_archived_brands: bool = False,
    brand_id: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    status: str | None = None,
    is_available: bool | None = None,
    test_drive_enabled: bool | None = None,
    fuel_type: str | None = None,
    transmission: str | None = None,
    drivetrain: str | None = None,
    search: str | None = None,
) -> int:
    return vehicle_repository.count_for_dealership(
        db,
        dealership_id,
        include_archived_brands=include_archived_brands,
        brand_id=brand_id,
        min_price=min_price,
        max_price=max_price,
        status=status,
        is_available=is_available,
        test_drive_enabled=test_drive_enabled,
        fuel_type=fuel_type,
        transmission=transmission,
        drivetrain=drivetrain,
        search=search,
    )


def list_public_vehicles(
    db: Session,
    dealership_id: int,
    *,
    brand_id: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    order: str = "asc",
    page: int | None = None,
    page_size: int | None = None,
    limit: int | None = None,
    include_images: bool = True,
) -> list[Vehicle]:
    vehicles = vehicle_repository.list_for_dealership(
        db,
        dealership_id,
        include_archived_brands=False,
        active_dealership_only=True,
        brand_id=brand_id,
        min_price=min_price,
        max_price=max_price,
        status="available",
        is_available=True,
        search=search,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
        limit=limit,
        include_images=include_images,
        include_status_history=False,
    )
    if not vehicles:
        dealership_service.get_active_dealership(db, dealership_id)
    return vehicles


def get_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
) -> Vehicle:
    ensure_dealership_access(current_user, dealership_id)
    dealership_service.get_active_dealership(db, dealership_id)
    return _get_vehicle(db, dealership_id, vehicle_id)


def update_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
    payload: VehicleUpdateRequest,
) -> Vehicle:
    ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise UnprocessableEntityError("At least one vehicle field is required")
    if "brand_id" in updates:
        if updates["brand_id"] is None:
            raise UnprocessableEntityError("brand_id cannot be null")
        brand = _get_active_brand(db, dealership_id, updates.pop("brand_id"))
        vehicle.brand_id = brand.id
        vehicle.make = brand.name

    # Handle status transition if provided in updates
    status_changed = False
    prev_status = vehicle.status or "available"
    if "status" in updates:
        new_status = updates.pop("status")
        if new_status:
            new_status = new_status.lower()
            if new_status != prev_status:
                status_changed = True
                if new_status == "available":
                    _ensure_brand_active(db, vehicle.brand_id)
                    vehicle.is_available = True
                else:
                    vehicle.is_available = False
                    if new_status in {"sold", "unavailable"}:
                        vehicle.test_drive_enabled = False
                vehicle.status = new_status
    elif "is_available" in updates:
        # Keep status and is_available synced when status was not explicitly passed
        new_avail = updates.get("is_available")
        if new_avail and vehicle.status != "available":
            status_changed = True
            new_status = "available"
            _ensure_brand_active(db, vehicle.brand_id)
            vehicle.status = new_status
        elif not new_avail and vehicle.status == "available":
            status_changed = True
            new_status = "unavailable"
            vehicle.status = new_status

    for field, value in updates.items():
        if value is None and field not in {"variant", "description"}:
            raise UnprocessableEntityError(f"{field} cannot be null")
        setattr(vehicle, field, value)
    if updates.get("is_available") is True or updates.get("test_drive_enabled") is True:
        _ensure_brand_active(db, vehicle.brand_id)
    try:
        saved_vehicle = vehicle_repository.save(db, vehicle)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Stock number already exists") from exc

    if status_changed:
        history = VehicleStatusHistory(
            dealership_id=dealership_id,
            vehicle_id=saved_vehicle.id,
            changed_by_user_id=current_user.id,
            previous_status=prev_status,
            new_status=saved_vehicle.status,
            notes="Updated via vehicle details update",
        )
        vehicle_repository.save_status_history(db, history)
        audit_service.log_event(
            db,
            action="vehicle.status_changed",
            resource_type="vehicle",
            resource_id=str(saved_vehicle.id),
            dealership_id=dealership_id,
            actor=current_user,
            details={
                "previous_status": prev_status,
                "new_status": saved_vehicle.status,
                "reason": "vehicle_update",
            },
        )
        if saved_vehicle.status in {"sold", "unavailable"}:
            _cleanup_bookings_and_slots_on_unavailable(db, dealership_id, saved_vehicle)

    return saved_vehicle


def transition_vehicle_status(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
    payload: VehicleStatusTransitionRequest,
) -> Vehicle:
    ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    prev_status = vehicle.status or "available"
    new_status = payload.status.lower()

    if prev_status == new_status:
        return vehicle

    if new_status == "available":
        _ensure_brand_active(db, vehicle.brand_id)
        vehicle.is_available = True
    else:
        vehicle.is_available = False
        if new_status in {"sold", "unavailable"}:
            vehicle.test_drive_enabled = False

    vehicle.status = new_status
    saved = vehicle_repository.save(db, vehicle)

    history = VehicleStatusHistory(
        dealership_id=dealership_id,
        vehicle_id=vehicle.id,
        changed_by_user_id=current_user.id,
        previous_status=prev_status,
        new_status=new_status,
        notes=payload.notes,
    )
    vehicle_repository.save_status_history(db, history)

    audit_service.log_event(
        db,
        action="vehicle.status_changed",
        resource_type="vehicle",
        resource_id=str(vehicle.id),
        dealership_id=dealership_id,
        actor=current_user,
        details={
            "previous_status": prev_status,
            "new_status": new_status,
            "notes": payload.notes,
            "model": f"{vehicle.model_year} {vehicle.make} {vehicle.model}",
            "stock_number": vehicle.stock_number,
        },
    )
    if new_status in {"sold", "unavailable"}:
        _cleanup_bookings_and_slots_on_unavailable(db, dealership_id, saved)
    try:
        outbox_service.enqueue_event(
            db,
            dealership_id=dealership_id,
            event_type=f"vehicle.{new_status}" if new_status == "sold" else "vehicle.status_changed",
            aggregate_type="vehicle",
            aggregate_id=saved.id,
            payload={
                "vehicle_id": saved.id,
                "previous_status": prev_status,
                "new_status": new_status,
                "stock_number": saved.stock_number,
            },
        )
    except Exception as exc:
        logger.warning("Outbox enqueue failed for vehicle %s: %s", saved.id, exc)
    return saved


def get_vehicle_status_history(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
) -> list[VehicleStatusHistory]:
    ensure_dealership_access(current_user, dealership_id)
    _get_vehicle(db, dealership_id, vehicle_id)
    return vehicle_repository.list_status_history_for_vehicle(db, dealership_id, vehicle_id)


def delete_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
) -> None:
    ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    prev_status = vehicle.status or "available"
    vehicle.status = "unavailable"
    vehicle.is_available = False
    vehicle.test_drive_enabled = False
    vehicle_repository.save(db, vehicle)

    history = VehicleStatusHistory(
        dealership_id=dealership_id,
        vehicle_id=vehicle.id,
        changed_by_user_id=current_user.id,
        previous_status=prev_status,
        new_status="unavailable",
        notes="Vehicle deleted/archived",
    )
    vehicle_repository.save_status_history(db, history)
    audit_service.log_event(
        db,
        action="vehicle.deleted",
        resource_type="vehicle",
        resource_id=str(vehicle.id),
        dealership_id=dealership_id,
        actor=current_user,
        details={"previous_status": prev_status},
    )
    _cleanup_bookings_and_slots_on_unavailable(db, dealership_id, vehicle)


def update_vehicle_availability(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
    available: bool,
) -> Vehicle:
    ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    prev_status = vehicle.status or "available"
    new_status = "available" if available else "unavailable"

    if available:
        _ensure_brand_active(db, vehicle.brand_id)
        vehicle.is_available = True
    else:
        vehicle.is_available = False

    if prev_status != new_status:
        vehicle.status = new_status
        history = VehicleStatusHistory(
            dealership_id=dealership_id,
            vehicle_id=vehicle.id,
            changed_by_user_id=current_user.id,
            previous_status=prev_status,
            new_status=new_status,
            notes="Toggled availability flag",
        )
        vehicle_repository.save_status_history(db, history)
        audit_service.log_event(
            db,
            action="vehicle.status_changed",
            resource_type="vehicle",
            resource_id=str(vehicle.id),
            dealership_id=dealership_id,
            actor=current_user,
            details={
                "previous_status": prev_status,
                "new_status": new_status,
                "notes": "Toggled availability flag",
            },
        )
    return vehicle_repository.save(db, vehicle)


def _get_vehicle(db: Session, dealership_id: int, vehicle_id: int) -> Vehicle:
    vehicle = vehicle_repository.get_for_dealership(db, dealership_id, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    return vehicle


def _get_active_brand(db: Session, dealership_id: int, brand_id: int) -> Brand:
    brand = vehicle_repository.get_active_brand(db, dealership_id, brand_id)
    if brand is None:
        raise UnprocessableEntityError(
            "brand_id must reference an active brand in this dealership"
        )
    return brand


def _ensure_brand_active(db: Session, brand_id: int) -> None:
    brand = vehicle_repository.get_brand_by_id(db, brand_id)
    if brand is None or not brand.is_active or brand.is_deleted:
        raise ConflictError(
            "Vehicles with inactive brands cannot be marked available or test-drive enabled"
        )


def _cleanup_bookings_and_slots_on_unavailable(
    db: Session,
    dealership_id: int,
    vehicle: Vehicle,
) -> None:
    """
    When a vehicle is sold or marked unavailable, deactivate its future slots,
    release active slot holds, and cancel + notify any remaining booked future test drives.
    """
    now = datetime.now(timezone.utc)
    future_slots = list(
        db.scalars(
            select(TestDriveSlot).where(
                TestDriveSlot.dealership_id == dealership_id,
                TestDriveSlot.vehicle_id == vehicle.id,
                TestDriveSlot.starts_at > now,
            )
        )
    )
    slot_ids = [s.id for s in future_slots]
    slot_map = {s.id: s for s in future_slots}

    for slot in future_slots:
        slot.is_active = False

    if slot_ids:
        active_holds = list(
            db.scalars(
                select(TestDriveSlotHold).where(
                    TestDriveSlotHold.dealership_id == dealership_id,
                    TestDriveSlotHold.slot_id.in_(slot_ids),
                    TestDriveSlotHold.status == "active",
                )
            )
        )
        for hold in active_holds:
            hold.status = "released"

    booked_future = list(
        db.scalars(
            select(TestDriveBooking)
            .join(TestDriveSlot, TestDriveSlot.id == TestDriveBooking.slot_id)
            .where(
                TestDriveBooking.dealership_id == dealership_id,
                TestDriveBooking.vehicle_id == vehicle.id,
                TestDriveBooking.status == "booked",
                TestDriveSlot.starts_at > now,
            )
        )
    )

    notifications: list[tuple[str, str, datetime]] = []
    for booking in booked_future:
        booking.status = "cancelled"
        booking.cancelled_at = now
        slot = slot_map.get(booking.slot_id)
        if slot is not None and slot.booked_count > 0:
            slot.booked_count -= 1
        customer = user_repository.get_by_id(db, booking.customer_id)
        if customer is not None and slot is not None:
            notifications.append((customer.email, customer.name, slot.starts_at))

    if future_slots or booked_future:
        db.commit()

    if notifications:
        dealership = dealership_repository.get_by_id(db, dealership_id)
        if dealership is not None:
            zone = ZoneInfo(dealership.timezone)
            vehicle_label = f"{vehicle.model_year} {vehicle.make} {vehicle.model}"
            for idx, (cust_email, cust_name, starts_at) in enumerate(notifications):
                try:
                    utc_start = (
                        starts_at.replace(tzinfo=timezone.utc)
                        if starts_at.tzinfo is None
                        else starts_at.astimezone(timezone.utc)
                    )
                    email_service.send_test_drive_cancelled(
                        recipient=cust_email,
                        customer_name=cust_name,
                        dealership_name=dealership.name,
                        vehicle_label=vehicle_label,
                        starts_at_local=utc_start.astimezone(zone).strftime("%b %d, %Y at %I:%M %p"),
                        timezone_name=dealership.timezone,
                        booking_id=booked_future[idx].id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to send cancellation notice on vehicle %s unavailable: %s",
                        vehicle.id,
                        exc,
                    )
