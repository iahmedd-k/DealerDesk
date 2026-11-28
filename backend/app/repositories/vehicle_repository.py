from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, noload

from app.models.workspace import Brand, Dealership, Vehicle, VehicleStatusHistory


def list_for_dealership(
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
    sort_by: str | None = None,
    order: str = "asc",
    page: int | None = None,
    page_size: int | None = None,
    limit: int | None = None,
    active_dealership_only: bool = False,
    include_images: bool = True,
    include_status_history: bool = True,
) -> list[Vehicle]:
    query = select(Vehicle).where(Vehicle.dealership_id == dealership_id)
    if active_dealership_only:
        query = query.join(
            Dealership, Dealership.id == Vehicle.dealership_id
        ).where(Dealership.is_active.is_(True))
    if not include_archived_brands:
        query = query.join(Brand, Brand.id == Vehicle.brand_id).where(
            Brand.is_active.is_(True),
            Brand.is_deleted.is_(False),
        )
    if brand_id is not None:
        query = query.where(Vehicle.brand_id == brand_id)
    if min_price is not None:
        query = query.where(Vehicle.price >= min_price)
    if max_price is not None:
        query = query.where(Vehicle.price <= max_price)
    if status is not None:
        query = query.where(Vehicle.status == status)
    if is_available is not None:
        query = query.where(Vehicle.is_available == is_available)
    if test_drive_enabled is not None:
        query = query.where(Vehicle.test_drive_enabled == test_drive_enabled)
    if fuel_type:
        query = query.where(Vehicle.fuel_type.ilike(fuel_type))
    if transmission:
        query = query.where(Vehicle.transmission.ilike(transmission))
    if drivetrain:
        query = query.where(Vehicle.drivetrain.ilike(drivetrain))
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Vehicle.model.ilike(search_pattern),
                Vehicle.make.ilike(search_pattern),
                Vehicle.variant.ilike(search_pattern),
                Vehicle.stock_number.ilike(search_pattern),
                Vehicle.vin.ilike(search_pattern),
            )
        )

    # Sorting
    sort_col = Vehicle.id
    if sort_by == "price":
        sort_col = Vehicle.price
    elif sort_by == "year" or sort_by == "model_year":
        sort_col = Vehicle.model_year
    elif sort_by == "model":
        sort_col = Vehicle.model

    if order.lower() == "desc":
        query = query.order_by(sort_col.desc(), Vehicle.id.desc())
    else:
        query = query.order_by(sort_col.asc(), Vehicle.id.asc())

    # Pagination
    if page is not None and page_size is not None:
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
    if limit is not None:
        query = query.limit(limit)

    if not include_images:
        query = query.options(noload(Vehicle.images))
    if not include_status_history:
        query = query.options(noload(Vehicle.status_history))

    return list(db.scalars(query))


def count_for_dealership(
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
    query = select(func.count(Vehicle.id)).where(Vehicle.dealership_id == dealership_id)
    if not include_archived_brands:
        query = query.join(Brand, Brand.id == Vehicle.brand_id).where(
            Brand.is_active.is_(True),
            Brand.is_deleted.is_(False),
        )
    if brand_id is not None:
        query = query.where(Vehicle.brand_id == brand_id)
    if min_price is not None:
        query = query.where(Vehicle.price >= min_price)
    if max_price is not None:
        query = query.where(Vehicle.price <= max_price)
    if status is not None:
        query = query.where(Vehicle.status == status)
    if is_available is not None:
        query = query.where(Vehicle.is_available == is_available)
    if test_drive_enabled is not None:
        query = query.where(Vehicle.test_drive_enabled == test_drive_enabled)
    if fuel_type:
        query = query.where(Vehicle.fuel_type.ilike(fuel_type))
    if transmission:
        query = query.where(Vehicle.transmission.ilike(transmission))
    if drivetrain:
        query = query.where(Vehicle.drivetrain.ilike(drivetrain))
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Vehicle.model.ilike(search_pattern),
                Vehicle.make.ilike(search_pattern),
                Vehicle.variant.ilike(search_pattern),
                Vehicle.stock_number.ilike(search_pattern),
                Vehicle.vin.ilike(search_pattern),
            )
        )
    return db.scalar(query) or 0


def get_for_dealership(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
) -> Vehicle | None:
    return db.scalar(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.dealership_id == dealership_id,
        )
    )


def get_active_brand(
    db: Session,
    dealership_id: int,
    brand_id: int,
) -> Brand | None:
    return db.scalar(
        select(Brand).where(
            Brand.id == brand_id,
            Brand.dealership_id == dealership_id,
            Brand.is_active.is_(True),
            Brand.is_deleted.is_(False),
        )
    )


def get_brand_by_id(db: Session, brand_id: int) -> Brand | None:
    return db.get(Brand, brand_id)


def save(db: Session, vehicle: Vehicle) -> Vehicle:
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def save_status_history(
    db: Session,
    history: VehicleStatusHistory,
) -> VehicleStatusHistory:
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def list_status_history_for_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
) -> list[VehicleStatusHistory]:
    stmt = (
        select(VehicleStatusHistory)
        .where(
            VehicleStatusHistory.dealership_id == dealership_id,
            VehicleStatusHistory.vehicle_id == vehicle_id,
        )
        .order_by(VehicleStatusHistory.created_at.desc(), VehicleStatusHistory.id.desc())
    )
    return list(db.scalars(stmt))
