from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.roles import STAFF_ROLES
from app.models.user import User
from app.models.workspace import CustomerLead, TestDriveBooking, Vehicle


def list_leads(
    db: Session,
    dealership_id: int,
    *,
    status: str | None,
    limit: int,
    offset: int,
    sales_rep_user_id: int | None,
) -> list[CustomerLead]:
    statement = select(CustomerLead).where(CustomerLead.dealership_id == dealership_id)
    if status is not None:
        statement = statement.where(CustomerLead.status == status)
    if sales_rep_user_id is not None:
        statement = statement.where(
            or_(
                CustomerLead.assigned_to_user_id == sales_rep_user_id,
                CustomerLead.assigned_to_user_id.is_(None),
            )
        )
    return list(
        db.scalars(
            statement.order_by(CustomerLead.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def get_lead(db: Session, dealership_id: int, lead_id: int) -> CustomerLead | None:
    return db.scalar(
        select(CustomerLead).where(
            CustomerLead.id == lead_id,
            CustomerLead.dealership_id == dealership_id,
        )
    )


def get_staff_user(db: Session, dealership_id: int, user_id: int) -> User | None:
    return db.scalar(
        select(User).where(
            User.id == user_id,
            User.dealership_id == dealership_id,
            User.role.in_(STAFF_ROLES),
            User.is_active.is_(True),
        )
    )


def get_vehicle(db: Session, dealership_id: int, vehicle_id: int) -> Vehicle | None:
    return db.scalar(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.dealership_id == dealership_id,
        )
    )


def get_booking(
    db: Session,
    dealership_id: int,
    booking_id: int,
) -> TestDriveBooking | None:
    return db.scalar(
        select(TestDriveBooking).where(
            TestDriveBooking.id == booking_id,
            TestDriveBooking.dealership_id == dealership_id,
        )
    )


def get_customer(db: Session, customer_id: int) -> User | None:
    return db.get(User, customer_id)


def save(db: Session, lead: CustomerLead) -> CustomerLead:
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
