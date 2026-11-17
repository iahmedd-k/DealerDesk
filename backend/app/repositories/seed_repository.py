from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Brand, Dealership, TestDriveSettings


def get_dealership_by_name(db: Session, name: str) -> Dealership | None:
    return db.scalar(select(Dealership).where(Dealership.name == name))


def create_dealership(
    db: Session,
    *,
    name: str,
    email: str,
) -> Dealership:
    dealership = Dealership(name=name, email=email, timezone="UTC")
    db.add(dealership)
    db.flush()
    db.add(TestDriveSettings(dealership_id=dealership.id))
    return dealership


def ensure_demo_brand(db: Session, dealership_id: int) -> None:
    brand_id = db.scalar(
        select(Brand.id).where(
            Brand.dealership_id == dealership_id,
            Brand.is_deleted.is_(False),
        )
    )
    if brand_id is None:
        db.add(Brand(dealership_id=dealership_id, name="Toyota"))


def save(db: Session, *entities: User | Dealership) -> None:
    db.add_all(entities)
    db.commit()
    for entity in entities:
        db.refresh(entity)
