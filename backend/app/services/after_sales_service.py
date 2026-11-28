from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_role_access
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.roles import STAFF_ROLES
from app.models.service import ServiceAppointment, ServiceWorkOrder, VehicleWarranty
from app.models.user import User
from app.models.workspace import Vehicle
from app.repositories import lead_repository
from app.schemas.after_sales import (
    ServiceAppointmentCreate,
    ServiceAppointmentUpdate,
    ServiceWorkOrderCreate,
    ServiceWorkOrderUpdate,
    VehicleWarrantyCreate,
    VehicleWarrantyUpdate,
)

T = TypeVar("T")


def _ensure_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int | None,
) -> Vehicle | None:
    if vehicle_id is None:
        return None
    vehicle = db.scalar(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.dealership_id == dealership_id,
        )
    )
    if vehicle is None:
        raise NotFoundError("Vehicle not found in this dealership")
    return vehicle


def _ensure_assignee(
    db: Session,
    dealership_id: int,
    user_id: int | None,
) -> None:
    if user_id is not None and lead_repository.get_staff_user(
        db, dealership_id, user_id
    ) is None:
        raise NotFoundError("Active dealership staff member not found")


def _commit_new(db: Session, item: T, conflict_message: str) -> T:
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(conflict_message) from exc
    db.refresh(item)
    return item


def _get_appointment(
    db: Session,
    dealership_id: int,
    appointment_id: int,
) -> ServiceAppointment:
    item = db.scalar(
        select(ServiceAppointment).where(
            ServiceAppointment.id == appointment_id,
            ServiceAppointment.dealership_id == dealership_id,
        )
    )
    if item is None:
        raise NotFoundError("Service appointment not found")
    return item


def _get_work_order(
    db: Session,
    dealership_id: int,
    work_order_id: int,
) -> ServiceWorkOrder:
    item = db.scalar(
        select(ServiceWorkOrder).where(
            ServiceWorkOrder.id == work_order_id,
            ServiceWorkOrder.dealership_id == dealership_id,
        )
    )
    if item is None:
        raise NotFoundError("Service work order not found")
    return item


def _get_warranty(
    db: Session,
    dealership_id: int,
    warranty_id: int,
) -> VehicleWarranty:
    item = db.scalar(
        select(VehicleWarranty).where(
            VehicleWarranty.id == warranty_id,
            VehicleWarranty.dealership_id == dealership_id,
        )
    )
    if item is None:
        raise NotFoundError("Vehicle warranty not found")
    return item


def list_appointments(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    status: str | None = None,
) -> list[ServiceAppointment]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    query = select(ServiceAppointment).where(
        ServiceAppointment.dealership_id == dealership_id
    )
    if status is not None:
        query = query.where(ServiceAppointment.status == status)
    return list(
        db.scalars(
            query.order_by(
                ServiceAppointment.scheduled_at.desc(),
                ServiceAppointment.id.desc(),
            )
        )
    )


def create_appointment(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: ServiceAppointmentCreate,
) -> ServiceAppointment:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    _ensure_vehicle(db, dealership_id, payload.vehicle_id)
    _ensure_assignee(db, dealership_id, payload.assigned_to_user_id)
    item = ServiceAppointment(
        dealership_id=dealership_id,
        vehicle_id=payload.vehicle_id,
        customer_name=payload.customer_name,
        customer_email=str(payload.customer_email).lower()
        if payload.customer_email
        else None,
        customer_phone=payload.customer_phone,
        scheduled_at=payload.scheduled_at,
        concern=payload.concern,
        assigned_to_user_id=payload.assigned_to_user_id,
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )
    return _commit_new(db, item, "Could not create service appointment")


def update_appointment(
    db: Session,
    dealership_id: int,
    appointment_id: int,
    current_user: User,
    payload: ServiceAppointmentUpdate,
) -> ServiceAppointment:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    item = _get_appointment(db, dealership_id, appointment_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequestError("At least one service appointment field is required")
    if "scheduled_at" in changes and changes["scheduled_at"] is None:
        raise BadRequestError("Appointment schedule cannot be null")
    if "status" in changes:
        new_status = changes["status"]
        if new_status is None:
            raise BadRequestError("Appointment status cannot be null")
        allowed = {
            "scheduled": {"confirmed", "completed", "cancelled", "no_show"},
            "confirmed": {"completed", "cancelled", "no_show"},
        }
        if new_status != item.status and new_status not in allowed.get(item.status, set()):
            raise ConflictError("This service appointment status cannot be changed")
        if new_status == "completed" and item.status != "completed":
            item.completed_at = datetime.now(timezone.utc)
    if "assigned_to_user_id" in changes:
        _ensure_assignee(db, dealership_id, changes["assigned_to_user_id"])
    for field, value in changes.items():
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


def list_work_orders(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    status: str | None = None,
    follow_up_due: bool = False,
) -> list[ServiceWorkOrder]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    query = select(ServiceWorkOrder).where(
        ServiceWorkOrder.dealership_id == dealership_id
    )
    if status is not None:
        query = query.where(ServiceWorkOrder.status == status)
    if follow_up_due:
        query = query.where(
            ServiceWorkOrder.follow_up_status == "pending",
            ServiceWorkOrder.follow_up_at <= datetime.now(timezone.utc),
        )
    return list(
        db.scalars(
            query.order_by(ServiceWorkOrder.created_at.desc(), ServiceWorkOrder.id.desc())
        )
    )


def create_work_order(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: ServiceWorkOrderCreate,
) -> ServiceWorkOrder:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    appointment = (
        _get_appointment(db, dealership_id, payload.appointment_id)
        if payload.appointment_id is not None
        else None
    )
    if appointment is not None:
        if appointment.status in {"cancelled", "no_show"}:
            raise ConflictError("Cannot create a work order for a cancelled or missed appointment")
        existing = db.scalar(
            select(ServiceWorkOrder.id).where(
                ServiceWorkOrder.dealership_id == dealership_id,
                ServiceWorkOrder.appointment_id == appointment.id,
            )
        )
        if existing is not None:
            raise ConflictError("A work order already exists for this appointment")
        if (
            payload.vehicle_id is not None
            and appointment.vehicle_id is not None
            and payload.vehicle_id != appointment.vehicle_id
        ):
            raise BadRequestError("Work order vehicle must match the appointment vehicle")
        vehicle_id = (
            payload.vehicle_id
            if payload.vehicle_id is not None
            else appointment.vehicle_id
        )
        customer_name = appointment.customer_name
        customer_email = appointment.customer_email
        customer_phone = appointment.customer_phone
        concern = payload.concern
    else:
        vehicle_id = payload.vehicle_id
        customer_name = payload.customer_name
        customer_email = (
            str(payload.customer_email).lower() if payload.customer_email else None
        )
        customer_phone = payload.customer_phone
        concern = payload.concern
    _ensure_vehicle(db, dealership_id, vehicle_id)

    item = ServiceWorkOrder(
        dealership_id=dealership_id,
        appointment_id=appointment.id if appointment else None,
        vehicle_id=vehicle_id,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        concern=concern,
        diagnosis=payload.diagnosis,
        labor_cost=payload.labor_cost,
        parts_cost=payload.parts_cost,
        follow_up_at=payload.follow_up_at,
        follow_up_status=payload.follow_up_status,
        follow_up_notes=payload.follow_up_notes,
        created_by_user_id=current_user.id,
    )
    return _commit_new(
        db,
        item,
        "A work order already exists for this appointment",
    )


def update_work_order(
    db: Session,
    dealership_id: int,
    work_order_id: int,
    current_user: User,
    payload: ServiceWorkOrderUpdate,
) -> ServiceWorkOrder:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    item = _get_work_order(db, dealership_id, work_order_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequestError("At least one work order field is required")
    if any(
        field in changes and changes[field] is None
        for field in ("labor_cost", "parts_cost", "follow_up_status")
    ):
        raise BadRequestError("Work order costs and follow-up status cannot be null")

    follow_up_status = changes.get("follow_up_status", item.follow_up_status)
    follow_up_at = changes.get("follow_up_at", item.follow_up_at)
    if "follow_up_at" in changes and "follow_up_status" not in changes:
        follow_up_status = "pending" if follow_up_at is not None else "not_required"
        changes["follow_up_status"] = follow_up_status
    if follow_up_status == "pending" and follow_up_at is None:
        raise BadRequestError("A scheduled time is required for pending follow-up")
    if follow_up_status == "not_required":
        changes["follow_up_at"] = None

    if changes.get("status") == item.status:
        changes.pop("status")
    if item.status == "cancelled":
        raise ConflictError("Cancelled work orders cannot be changed")
    if item.status == "completed" and any(
        field in changes
        for field in {"status", "diagnosis", "labor_cost", "parts_cost"}
    ):
        raise ConflictError("Completed work orders only allow follow-up updates")
    if "status" in changes:
        new_status = changes["status"]
        if new_status is None:
            raise BadRequestError("Work order status cannot be null")
        allowed = {
            "open": {"in_progress", "completed", "cancelled"},
            "in_progress": {"completed", "cancelled"},
        }
        if new_status not in allowed.get(item.status, set()):
            raise ConflictError("This work order status cannot be changed")
        if new_status == "completed":
            item.completed_at = datetime.now(timezone.utc)
    for field, value in changes.items():
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


def list_warranties(
    db: Session,
    dealership_id: int,
    current_user: User,
) -> list[VehicleWarranty]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    return list(
        db.scalars(
            select(VehicleWarranty)
            .where(VehicleWarranty.dealership_id == dealership_id)
            .order_by(VehicleWarranty.end_date.asc(), VehicleWarranty.id.desc())
        )
    )


def create_warranty(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: VehicleWarrantyCreate,
) -> VehicleWarranty:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    if _ensure_vehicle(db, dealership_id, payload.vehicle_id) is None:
        raise NotFoundError("Vehicle not found in this dealership")
    item = VehicleWarranty(
        dealership_id=dealership_id,
        vehicle_id=payload.vehicle_id,
        provider=payload.provider,
        policy_number=payload.policy_number,
        coverage=payload.coverage,
        start_date=payload.start_date,
        end_date=payload.end_date,
        mileage_limit=payload.mileage_limit,
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )
    return _commit_new(db, item, "Could not create vehicle warranty")


def update_warranty(
    db: Session,
    dealership_id: int,
    warranty_id: int,
    current_user: User,
    payload: VehicleWarrantyUpdate,
) -> VehicleWarranty:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    item = _get_warranty(db, dealership_id, warranty_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequestError("At least one vehicle warranty field is required")
    if any(
        field in changes and changes[field] is None
        for field in ("provider", "coverage", "start_date", "end_date")
    ):
        raise BadRequestError("Warranty provider, coverage, and dates cannot be null")
    start_date = changes.get("start_date", item.start_date)
    end_date = changes.get("end_date", item.end_date)
    if end_date < start_date:
        raise BadRequestError("end_date must be on or after start_date")
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
