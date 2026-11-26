from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.roles import STAFF_ROLES
from app.models.user import User
from app.models.workspace import CustomerLead, LeadActivity, TestDriveBooking, Vehicle


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


def count_leads(
    db: Session,
    dealership_id: int,
    *,
    status: str | None,
    sales_rep_user_id: int | None,
) -> int:
    statement = select(func.count(CustomerLead.id)).where(
        CustomerLead.dealership_id == dealership_id
    )
    if status is not None:
        statement = statement.where(CustomerLead.status == status)
    if sales_rep_user_id is not None:
        statement = statement.where(
            or_(
                CustomerLead.assigned_to_user_id == sales_rep_user_id,
                CustomerLead.assigned_to_user_id.is_(None),
            )
        )
    return db.scalar(statement) or 0


def save_activity(db: Session, activity: LeadActivity) -> LeadActivity:
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def list_activities(
    db: Session,
    dealership_id: int,
    lead_id: int,
) -> list[LeadActivity]:
    statement = (
        select(LeadActivity)
        .where(
            LeadActivity.dealership_id == dealership_id,
            LeadActivity.lead_id == lead_id,
        )
        .order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc())
    )
    return list(db.scalars(statement))


def find_least_loaded_sales_rep(db: Session, dealership_id: int) -> User | None:
    """
    Returns the active sales_rep (or manager fallback) with the fewest open leads
    in this dealership for automated round-robin / load-balanced lead assignment.
    """
    reps = list(
        db.scalars(
            select(User)
            .where(
                User.dealership_id == dealership_id,
                User.role == "sales_rep",
                User.is_active.is_(True),
                User.is_available.is_(True),
            )
            .order_by(User.id.asc())
        )
    )
    if not reps:
        reps = list(
            db.scalars(
                select(User)
                .where(
                    User.dealership_id == dealership_id,
                    User.role.in_(["manager", "dealership_admin"]),
                    User.is_active.is_(True),
                )
                .order_by(User.id.asc())
            )
        )
    if not reps:
        return None

    open_counts = dict(
        db.execute(
            select(CustomerLead.assigned_to_user_id, func.count(CustomerLead.id))
            .where(
                CustomerLead.dealership_id == dealership_id,
                CustomerLead.assigned_to_user_id.in_([r.id for r in reps]),
                CustomerLead.status.notin_(["won", "lost"]),
            )
            .group_by(CustomerLead.assigned_to_user_id)
        ).all()
    )
    return min(reps, key=lambda rep: (open_counts.get(rep.id, 0), rep.id))


def delete_lead(db: Session, lead: CustomerLead) -> None:
    db.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).delete(
        synchronize_session=False
    )
    db.delete(lead)
    db.commit()
