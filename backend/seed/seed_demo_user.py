"""Create or refresh the shared customer and dealership demo accounts."""

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import User
from app.services.seed_service import seed_demo_users as create_demo_users
from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_NAME,
    CUSTOMER_DEMO_PASSWORD,
    DEALERSHIP_DEMO_BUSINESS_EMAIL,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_NAME,
    DEALERSHIP_DEMO_PASSWORD,
)


def seed_demo_users() -> tuple[User, User]:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return create_demo_users(
            db,
            customer_name=CUSTOMER_DEMO_NAME,
            customer_email=CUSTOMER_DEMO_EMAIL,
            customer_password=CUSTOMER_DEMO_PASSWORD,
            dealership_name=DEALERSHIP_DEMO_NAME,
            dealership_business_email=DEALERSHIP_DEMO_BUSINESS_EMAIL,
            dealership_admin_email=DEALERSHIP_DEMO_EMAIL,
            dealership_admin_password=DEALERSHIP_DEMO_PASSWORD,
        )
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
