from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER_ROLE, DEALERSHIP_ADMIN_ROLE
from app.models.user import User
from app.models.workspace import Dealership
from app.repositories import seed_repository, user_repository
from app.services.auth_service import hash_password


def seed_demo_users(
    db: Session,
    *,
    customer_name: str,
    customer_email: str,
    customer_password: str,
    dealership_name: str,
    dealership_business_email: str,
    dealership_admin_email: str,
    dealership_admin_password: str,
) -> tuple[User, User]:
    dealership = _get_or_create_dealership(
        db,
        dealership_name,
        dealership_business_email,
    )
    customer = _refresh_user(
        db,
        name=customer_name,
        email=customer_email,
        password=customer_password,
        role=CUSTOMER_ROLE,
    )
    dealership_admin = _refresh_user(
        db,
        name=dealership_name,
        email=dealership_admin_email,
        password=dealership_admin_password,
        role=DEALERSHIP_ADMIN_ROLE,
        dealership_id=dealership.id,
    )
    seed_repository.save(db, dealership, customer, dealership_admin)
    return customer, dealership_admin


def _get_or_create_dealership(
    db: Session,
    name: str,
    business_email: str,
) -> Dealership:
    dealership = seed_repository.get_dealership_by_name(db, name)
    if dealership is None:
        dealership = seed_repository.create_dealership(
            db,
            name=name,
            email=business_email,
        )
    seed_repository.ensure_demo_brand(db, dealership.id)
    return dealership


def _refresh_user(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: str,
    dealership_id: int | None = None,
) -> User:
    user = user_repository.get_by_email(db, email)
    if user is None:
        return user_repository.create(
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
