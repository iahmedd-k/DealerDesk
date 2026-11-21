from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE
from app.models.user import User
from app.models.workspace import (
    Brand,
    Dealership,
    TestDriveBooking,
    TestDriveSettings,
    Vehicle,
)
from app.repositories import user_repository


def list_active(db: Session) -> list[Dealership]:
    return list(
        db.scalars(
            select(Dealership)
            .where(Dealership.is_active.is_(True))
            .order_by(Dealership.name)
        )
    )


def list_all(db: Session) -> list[Dealership]:
    return list(db.scalars(select(Dealership).order_by(Dealership.id.desc())))


def list_detailed(db: Session) -> list[dict]:
    dealerships = list_all(db)
    result = []
    for d in dealerships:
        brands_count = (
            db.scalar(
                select(func.count(Brand.id)).where(
                    Brand.dealership_id == d.id, Brand.is_deleted.is_(False)
                )
            )
            or 0
        )
        vehicles_count = (
            db.scalar(
                select(func.count(Vehicle.id)).where(Vehicle.dealership_id == d.id)
            )
            or 0
        )
        staff_count = (
            db.scalar(
                select(func.count(User.id)).where(User.dealership_id == d.id)
            )
            or 0
        )
        result.append(
            {
                "id": d.id,
                "name": d.name,
                "email": d.email,
                "phone": d.phone,
                "address": d.address,
                "timezone": d.timezone,
                "is_active": d.is_active,
                "subscription_plan": d.subscription_plan or "pro",
                "subscription_status": d.subscription_status or "active",
                "monthly_price": float(d.monthly_price or 499.0),
                "max_brands": d.max_brands or 10,
                "max_vehicles": d.max_vehicles or 250,
                "created_at": d.created_at,
                "brands_count": brands_count,
                "vehicles_count": vehicles_count,
                "staff_count": staff_count,
            }
        )
    return result


def get_platform_metrics(db: Session) -> dict:
    total_dealerships = db.scalar(select(func.count(Dealership.id))) or 0
    active_dealerships = (
        db.scalar(
            select(func.count(Dealership.id)).where(Dealership.is_active.is_(True))
        )
        or 0
    )
    total_mrr = (
        db.scalar(
            select(func.coalesce(func.sum(Dealership.monthly_price), 0)).where(
                Dealership.is_active.is_(True),
                Dealership.subscription_status == "active",
            )
        )
        or 0.0
    )
    total_vehicles = db.scalar(select(func.count(Vehicle.id))) or 0
    total_bookings = db.scalar(select(func.count(TestDriveBooking.id))) or 0
    total_staff = (
        db.scalar(select(func.count(User.id)).where(User.dealership_id.is_not(None)))
        or 0
    )
    total_brands = (
        db.scalar(select(func.count(Brand.id)).where(Brand.is_deleted.is_(False)))
        or 0
    )

    plans: dict[str, int] = {"starter": 0, "pro": 0, "enterprise": 0}
    plan_rows = db.execute(
        select(Dealership.subscription_plan, func.count(Dealership.id)).group_by(
            Dealership.subscription_plan
        )
    ).all()
    for plan, count in plan_rows:
        if plan in plans:
            plans[plan] = count
        elif plan:
            plans[plan] = count

    return {
        "total_dealerships": total_dealerships,
        "active_dealerships": active_dealerships,
        "total_mrr": float(total_mrr),
        "total_vehicles": total_vehicles,
        "total_bookings": total_bookings,
        "total_staff": total_staff,
        "total_brands": total_brands,
        "plan_distribution": plans,
    }


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
