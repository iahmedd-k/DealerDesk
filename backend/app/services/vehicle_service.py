from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_access
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.roles import DEALERSHIP_MANAGEMENT_ROLES
from app.models.user import User
from app.models.workspace import Brand, Vehicle, VehicleStatusHistory
from app.repositories import brand_repository, vehicle_repository
from app.schemas.workspace import (
    VehicleCreateRequest,
    VehicleStatusTransitionRequest,
    VehicleUpdateRequest,
)
from app.services import audit_service, dealership_service


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
    payload_data = payload.model_dump(exclude={"brand_id", "status"})
    
    vehicle = Vehicle(
        dealership_id=dealership_id,
        brand_id=brand.id,
        make=brand.name,
        status=status_val,
        is_available=is_available,
        **payload_data,
    )
    try:
        saved_vehicle = vehicle_repository.save(db, vehicle)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Stock number already exists") from exc

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
) -> list[Vehicle]:
    dealership_service.get_active_dealership(db, dealership_id)
    return vehicle_repository.list_for_dealership(
        db,
        dealership_id,
        include_archived_brands=False,
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
    )


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
