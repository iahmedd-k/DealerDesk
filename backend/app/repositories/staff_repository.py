from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER_ROLE
from app.models.user import User
from app.models.workspace import Dealership, StaffInvitation


def list_staff(db: Session, dealership_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.dealership_id == dealership_id, User.role != CUSTOMER_ROLE)
            .order_by(User.id)
        )
    )


def get_latest_invitation_for_user(
    db: Session,
    user_id: int,
) -> StaffInvitation | None:
    return db.scalar(
        select(StaffInvitation)
        .where(StaffInvitation.user_id == user_id)
        .order_by(StaffInvitation.id.desc())
        .limit(1)
    )


def create_invitation(
    db: Session,
    *,
    dealership_id: int,
    inviter_id: int,
    name: str,
    email: str,
    role: str,
    password: str,
    activation_token: str,
    expires_at: datetime,
) -> tuple[User, StaffInvitation]:
    user = User(
        name=name,
        email=email,
        password=password,
        role=role,
        dealership_id=dealership_id,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    invitation = StaffInvitation(
        dealership_id=dealership_id,
        invited_by_user_id=inviter_id,
        user_id=user.id,
        email=email,
        role=role,
        activation_token=activation_token,
        expires_at=expires_at,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return user, invitation


def save(db: Session, *entities: User | StaffInvitation) -> None:
    db.add_all(entities)
    db.commit()


def get_dealership(db: Session, dealership_id: int) -> Dealership | None:
    return db.get(Dealership, dealership_id)


def list_invitations(db: Session, dealership_id: int) -> list[StaffInvitation]:
    return list(
        db.scalars(
            select(StaffInvitation)
            .where(StaffInvitation.dealership_id == dealership_id)
            .order_by(StaffInvitation.id.desc())
        )
    )


def get_invitation(
    db: Session,
    dealership_id: int,
    invitation_id: int,
) -> StaffInvitation | None:
    return db.scalar(
        select(StaffInvitation).where(
            StaffInvitation.id == invitation_id,
            StaffInvitation.dealership_id == dealership_id,
        )
    )


def get_staff_user(
    db: Session,
    dealership_id: int,
    user_id: int,
) -> User | None:
    return db.scalar(
        select(User).where(
            User.id == user_id,
            User.dealership_id == dealership_id,
            User.role != CUSTOMER_ROLE,
        )
    )


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
