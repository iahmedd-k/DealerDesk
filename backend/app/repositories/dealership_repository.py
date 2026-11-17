from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE
from app.models.user import User
from app.models.workspace import Brand, Dealership, TestDriveSettings
from app.repositories import user_repository


def list_active(db: Session) -> list[Dealership]:
    return list(
        db.scalars(
            select(Dealership)
            .where(Dealership.is_active.is_(True))
            .order_by(Dealership.name)
        )
    )


def get_by_id(db: Session, dealership_id: int) -> Dealership | None:
    return db.get(Dealership, dealership_id)


def get_active_by_id(db: Session, dealership_id: int) -> Dealership | None:
    dealership = get_by_id(db, dealership_id)
    if dealership is None or not dealership.is_active:
        return None
    return dealership


def create_registration(
    db: Session,
    *,
    name: str,
    email: str,
    phone: str | None,
    address: str | None,
    timezone: str,
    brand_names: list[str],
    admin_name: str,
    admin_email: str,
    admin_password: str,
) -> User:
    dealership = Dealership(
        name=name,
        email=email,
        phone=phone,
        address=address,
        timezone=timezone,
    )
    db.add(dealership)
    db.flush()
    db.add_all(
        Brand(dealership_id=dealership.id, name=brand_name)
        for brand_name in brand_names
    )
    admin = user_repository.create(
        db,
        name=admin_name,
        email=admin_email,
        password=admin_password,
        role=DEALERSHIP_ADMIN_ROLE,
        dealership_id=dealership.id,
        commit=False,
    )
    db.add(TestDriveSettings(dealership_id=dealership.id))
    db.commit()
    db.refresh(admin)
    return admin


def save(db: Session, dealership: Dealership) -> Dealership:
    db.add(dealership)
    db.commit()
    db.refresh(dealership)
    return dealership


def commit(db: Session) -> None:
    db.commit()
