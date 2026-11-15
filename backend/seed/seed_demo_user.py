"""Create or refresh the shared customer and dealership demo accounts."""

from sqlalchemy import select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Dealership, TestDriveSettings, User
from app.repositories.user_repository import create, get_by_email
from app.services.auth_service import hash_password
from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_NAME,
    CUSTOMER_DEMO_PASSWORD,
    DEALERSHIP_DEMO_BUSINESS_EMAIL,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_NAME,
    DEALERSHIP_DEMO_PASSWORD,
)


def _get_or_create_dealership(db) -> Dealership:
    dealership = db.scalar(
        select(Dealership).where(Dealership.name == DEALERSHIP_DEMO_NAME)
    )
    if dealership is None:
        dealership = Dealership(
            name=DEALERSHIP_DEMO_NAME,
            email=DEALERSHIP_DEMO_BUSINESS_EMAIL,
            timezone="UTC",
        )
        db.add(dealership)
        db.flush()
        db.add(TestDriveSettings(dealership_id=dealership.id))
    return dealership


def _refresh_user(
    db,
    *,
    name: str,
    email: str,
    password: str,
    role: str,
    dealership_id: int | None = None,
) -> User:
    user = get_by_email(db, email)
    if user is None:
        return create(
            db,
            name=name,
            email=email,
            password=hash_password(password),
            role=role,
            dealership_id=dealership_id,
            commit=False,
        )
    user.name = name
    user.password = hash_password(password)
    user.role = role
    user.dealership_id = dealership_id
    user.is_active = True
    user.must_change_password = False
    return user


def seed_demo_users() -> tuple[User, User]:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        dealership = _get_or_create_dealership(db)
        customer = _refresh_user(
            db,
            name=CUSTOMER_DEMO_NAME,
            email=CUSTOMER_DEMO_EMAIL,
            password=CUSTOMER_DEMO_PASSWORD,
            role="customer",
        )
        dealership_admin = _refresh_user(
            db,
            name=DEALERSHIP_DEMO_NAME,
            email=DEALERSHIP_DEMO_EMAIL,
            password=DEALERSHIP_DEMO_PASSWORD,
            role="dealership_admin",
            dealership_id=dealership.id,
        )
        db.commit()
        db.refresh(customer)
        db.refresh(dealership_admin)
        return customer, dealership_admin
    finally:
        db.close()


def seed_demo_user() -> User:
    """Seed both accounts and return the customer for compatibility."""
    customer, _ = seed_demo_users()
    return customer


if __name__ == "__main__":
    customer, dealership_admin = seed_demo_users()
    print(f"Seeded customer demo {customer.email} with id {customer.id}")
    print(
        f"Seeded dealership demo {dealership_admin.email} "
        f"with id {dealership_admin.id}"
    )
