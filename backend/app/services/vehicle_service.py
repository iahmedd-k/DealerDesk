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
from app.models.workspace import Brand, Vehicle
from app.repositories import vehicle_repository
from app.schemas.workspace import VehicleCreateRequest, VehicleUpdateRequest
from app.services import dealership_service


def create_vehicle(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: VehicleCreateRequest,
) -> Vehicle:
    ensure_dealership_access(current_user, dealership_id)
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
    include_archived_brands: bool = False,
    brand_id: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
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
    ensure_dealership_access(current_user, dealership_id)
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
    ensure_dealership_access(current_user, dealership_id)
    vehicle = _get_vehicle(db, dealership_id, vehicle_id)
    if available:
        _ensure_brand_active(db, vehicle.brand_id)
    vehicle.is_available = available
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
