from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import Brand, Vehicle


def list_for_dealership(
    db: Session,
    dealership_id: int,
    *,
    include_archived_brands: bool,
) -> list[Vehicle]:
    query = select(Vehicle).where(Vehicle.dealership_id == dealership_id)
    if not include_archived_brands:
        query = query.join(Brand, Brand.id == Vehicle.brand_id).where(
            Brand.is_active.is_(True),
            Brand.is_deleted.is_(False),
        )
    return list(db.scalars(query.order_by(Vehicle.id)))


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
