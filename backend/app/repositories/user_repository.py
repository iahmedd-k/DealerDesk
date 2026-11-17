from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER_ROLE
from app.models.user import User
from app.models.workspace import Dealership


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def create(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: str = CUSTOMER_ROLE,
    dealership_id: int | None = None,
    must_change_password: bool = False,
    commit: bool = True,
) -> User:
    user = User(
        name=name,
        email=email,
        password=password,
        role=role,
        dealership_id=dealership_id,
        must_change_password=must_change_password,
    )
    db.add(user)
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def list_for_dealership(db: Session, dealership_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.dealership_id == dealership_id)
            .order_by(User.id)
        )
    )


def save(db: Session, user: User, *, refresh: bool = False) -> User:
    db.add(user)
    db.commit()
    if refresh:
        db.refresh(user)
    return user


def lock_dealership(db: Session, dealership_id: int) -> None:
    db.scalar(
        select(Dealership.id)
        .where(Dealership.id == dealership_id)
        .with_for_update()
    )


def has_another_active_admin(
    db: Session,
    dealership_id: int,
    excluded_user_id: int,
) -> bool:
    another_admin_id = db.scalar(
        select(User.id)
        .where(
            User.dealership_id == dealership_id,
            User.role == "dealership_admin",
            User.is_active.is_(True),
            User.id != excluded_user_id,
        )
        .limit(1)
    )
    return another_admin_id is not None
