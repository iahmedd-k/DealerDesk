from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.authorization import ensure_dealership_access
from app.core.roles import DEALERSHIP_MANAGEMENT_ROLES
from app.models.user import User
from app.models.workspace import Brand, Vehicle
from app.repositories import dealership_repository, vehicle_repository
from app.schemas.workspace import VehicleCreateRequest, VehicleUpdateRequest


def create_vehicle(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: VehicleCreateRequest,
) -> Vehicle:
    _ensure_dealership_access(current_user, dealership_id)
    brand = _get_active_brand(db, dealership_id, payload.brand_id)
    vehicle = Vehicle(
        dealership_id=dealership_id,
        brand_id=brand.id,
        make=brand.name,
        **payload.model_dump(exclude={"brand_id"}),
    )
    try:
        return vehicle_repository.save(db, vehicle)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Stock number already exists") from exc


def list_vehicles(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    include_archived_brands: bool,
) -> list[Vehicle]:
    _ensure_dealership_access(current_user, dealership_id)
    _get_active_dealership(db, dealership_id)
    if (
        include_archived_brands
        and current_user.role not in DEALERSHIP_MANAGEMENT_ROLES
    ):
        raise ForbiddenError("A dealership manager role is required")
    return vehicle_repository.list_for_dealership(
        db,
        dealership_id,
        include_archived_brands=include_archived_brands,
    )


def get_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
) -> Vehicle:
    _ensure_dealership_access(current_user, dealership_id)
    _get_active_dealership(db, dealership_id)
    return _get_vehicle(db, dealership_id, vehicle_id)


def update_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
    payload: VehicleUpdateRequest,
) -> Vehicle:
    _ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    updates = payload.model_dump(exclude_unset=True)
    if "brand_id" in updates:
        if updates["brand_id"] is None:
            raise UnprocessableEntityError("brand_id cannot be null")
        brand = _get_active_brand(db, dealership_id, updates.pop("brand_id"))
        vehicle.brand_id = brand.id
        vehicle.make = brand.name
    for field, value in updates.items():
        if value is not None:
            setattr(vehicle, field, value)
    if updates.get("is_available") is True or updates.get("test_drive_enabled") is True:
        _ensure_brand_active(db, vehicle.brand_id)
    try:
        return vehicle_repository.save(db, vehicle)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Stock number already exists") from exc


def delete_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
) -> None:
    _ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    vehicle.is_available = False
    vehicle.test_drive_enabled = False
    vehicle_repository.save(db, vehicle)


def update_vehicle_availability(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
    available: bool,
) -> Vehicle:
    _ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    if available:
        _ensure_brand_active(db, vehicle.brand_id)
    vehicle.is_available = available
    return vehicle_repository.save(db, vehicle)


def _ensure_dealership_access(current_user: User, dealership_id: int) -> None:
    ensure_dealership_access(current_user, dealership_id)


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


def _get_active_dealership(db: Session, dealership_id: int) -> None:
    if dealership_repository.get_active_by_id(db, dealership_id) is None:
        raise NotFoundError("Dealership not found")
