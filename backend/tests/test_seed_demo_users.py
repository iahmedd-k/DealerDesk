from app.models import Dealership
from app.services.auth_service import verify_password
from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_PASSWORD,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_PASSWORD,
)
from seed.seed_demo_user import seed_demo_users


def test_seed_creates_separate_customer_and_dealership_accounts(db) -> None:
    customer, dealership_admin = seed_demo_users()
    dealership = db.get(Dealership, dealership_admin.dealership_id)

    assert customer.email == CUSTOMER_DEMO_EMAIL
    assert customer.role == "customer"
    assert customer.dealership_id is None
    assert verify_password(CUSTOMER_DEMO_PASSWORD, customer.password)
    assert dealership_admin.email == DEALERSHIP_DEMO_EMAIL
    assert dealership_admin.role == "dealership_admin"
    assert verify_password(DEALERSHIP_DEMO_PASSWORD, dealership_admin.password)
    assert dealership is not None


def test_seed_is_idempotent_and_refreshes_password(db) -> None:
    first_customer, first_admin = seed_demo_users()
    first_ids = (first_customer.id, first_admin.id)

    second_customer, second_admin = seed_demo_users()

    assert (second_customer.id, second_admin.id) == first_ids
    assert verify_password(CUSTOMER_DEMO_PASSWORD, second_customer.password)
    assert verify_password(DEALERSHIP_DEMO_PASSWORD, second_admin.password)
