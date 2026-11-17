from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.workspace import Brand, Dealership, TestDriveSlot, Vehicle


def list_for_dealership(
    db: Session,
    dealership_id: int,
    *,
    include_inactive: bool = False,
    include_deleted: bool = False,
) -> list[Brand]:
    query = select(Brand).where(Brand.dealership_id == dealership_id)
    if not include_deleted:
        query = query.where(Brand.is_deleted.is_(False))
    if not include_inactive:
        query = query.where(Brand.is_active.is_(True))
    return list(db.scalars(query.order_by(Brand.name, Brand.id)))


def lock_active_dealership(db: Session, dealership_id: int) -> Dealership | None:
    return db.scalar(
        select(Dealership)
        .where(
            Dealership.id == dealership_id,
            Dealership.is_active.is_(True),
        )
        .with_for_update()
    )


def count_not_deleted(db: Session, dealership_id: int) -> int:
    return db.scalar(
        select(func.count(Brand.id)).where(
            Brand.dealership_id == dealership_id,
            Brand.is_deleted.is_(False),
        )
    ) or 0


def get_for_dealership(
    db: Session,
    dealership_id: int,
    brand_id: int,
    *,
    include_deleted: bool = False,
) -> Brand | None:
    query = select(Brand).where(
        Brand.id == brand_id,
        Brand.dealership_id == dealership_id,
    )
    if not include_deleted:
        query = query.where(Brand.is_deleted.is_(False))
    return db.scalar(query)


def create(db: Session, brand: Brand) -> Brand:
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def save(
    db: Session,
    brand: Brand,
    *,
    update_vehicle_make: bool = False,
) -> Brand:
    if update_vehicle_make:
        db.execute(
            update(Vehicle)
            .where(Vehicle.brand_id == brand.id)
            .values(make=brand.name)
        )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def deactivate_future_slots(db: Session, brand_id: int) -> None:
    vehicle_ids = select(Vehicle.id).where(Vehicle.brand_id == brand_id)
    db.execute(
        update(TestDriveSlot)
        .where(
            TestDriveSlot.vehicle_id.in_(vehicle_ids),
            TestDriveSlot.starts_at > func.now(),
            TestDriveSlot.is_active.is_(True),
        )
        .values(is_active=False)
    )
