from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_role_access
from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.roles import CUSTOMER_ROLE, STAFF_ROLES
from app.models.user import User
from app.models.workspace import CustomerLead
from app.repositories import lead_repository
from app.schemas.workspace import (
    CustomerLeadCreateRequest,
    CustomerLeadUpdateRequest,
)
from app.services import assistant_service


def create_lead(
    db: Session,
    dealership_id: int,
    payload: CustomerLeadCreateRequest,
    current_user: User | None,
) -> CustomerLead:
    assistant_service.validate_assistant_scope(db, dealership_id, current_user)
    if current_user is not None and current_user.role == CUSTOMER_ROLE:
        if current_user.email.casefold() != str(payload.email).casefold():
            raise BadRequestError("A signed-in customer can only submit their own contact details")

    vehicle_id = payload.requested_vehicle_id
    if vehicle_id is not None and lead_repository.get_vehicle(
        db, dealership_id, vehicle_id
    ) is None:
        raise NotFoundError("Vehicle not found")

    now = datetime.now(timezone.utc)
    lead = CustomerLead(
        dealership_id=dealership_id,
        customer_id=(
            current_user.id
            if current_user is not None and current_user.role == CUSTOMER_ROLE
            else None
        ),
        requested_vehicle_id=vehicle_id,
        name=payload.name,
        email=str(payload.email).lower(),
        phone=payload.phone,
        message=payload.message,
        source=payload.source,
        consent_to_contact=True,
        consented_at=now,
        created_at=now,
        updated_at=now,
    )
    return lead_repository.save(db, lead)


def list_leads(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> list[CustomerLead]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    return lead_repository.list_leads(
        db,
        dealership_id,
        status=status,
        limit=limit,
        offset=offset,
        sales_rep_user_id=(
            current_user.id if current_user.role == "sales_rep" else None
        ),
    )


def update_lead(
    db: Session,
    dealership_id: int,
    lead_id: int,
    current_user: User,
    payload: CustomerLeadUpdateRequest,
) -> CustomerLead:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    if not payload.model_fields_set:
        raise BadRequestError("At least one lead field must be provided")
    lead = lead_repository.get_lead(db, dealership_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    _ensure_lead_visibility(lead, current_user)

    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is None:
        raise BadRequestError("Lead status cannot be null")
    if changes.get("status") == "test_drive_scheduled":
        raise BadRequestError("Link a test-drive booking to schedule a lead")
    if lead.test_drive_booking_id is not None and "status" in changes:
        raise ConflictError("A lead linked to a booking cannot change pipeline status")
    assigned_user_id = changes.get("assigned_to_user_id")
    if (
        current_user.role == "sales_rep"
        and "assigned_to_user_id" in changes
        and assigned_user_id not in {None, current_user.id}
    ):
        raise ForbiddenError("Sales representatives can only assign leads to themselves")
    if assigned_user_id is not None and lead_repository.get_staff_user(
        db, dealership_id, assigned_user_id
    ) is None:
        raise NotFoundError("Active dealership staff member not found")

    for field, value in changes.items():
        setattr(lead, field, value)
    if lead.status in {"lost", "won"}:
        lead.next_follow_up_at = None
    lead.updated_at = datetime.now(timezone.utc)
    return lead_repository.save(db, lead)


def convert_lead_to_booking(
    db: Session,
    dealership_id: int,
    lead_id: int,
    booking_id: int,
    current_user: User,
) -> CustomerLead:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    lead = lead_repository.get_lead(db, dealership_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    _ensure_lead_visibility(lead, current_user)
    booking = lead_repository.get_booking(db, dealership_id, booking_id)
    if booking is None:
        raise NotFoundError("Test-drive booking not found")
    if booking.status not in {"booked", "completed"}:
        raise UnprocessableEntityError("Only active or completed bookings can convert a lead")
    if lead.test_drive_booking_id is not None:
        if lead.test_drive_booking_id == booking.id:
            return lead
        raise ConflictError("Lead is already linked to another booking")
    if lead.status in {"lost", "won"}:
        raise ConflictError("A closed lead cannot be linked to a booking")
    customer = lead_repository.get_customer(db, booking.customer_id)
    if customer is None or customer.email.casefold() != lead.email.casefold():
        raise BadRequestError("The booking customer does not match the lead")
    if lead.customer_id is not None and lead.customer_id != customer.id:
        raise BadRequestError("The booking customer does not match the lead")

    lead.test_drive_booking_id = booking.id
    lead.status = "test_drive_scheduled"
    lead.next_follow_up_at = None
    lead.updated_at = datetime.now(timezone.utc)
    try:
        return lead_repository.save(db, lead)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("This test-drive booking is already linked to a lead") from exc


def _ensure_lead_visibility(lead: CustomerLead, current_user: User) -> None:
    if (
        current_user.role == "sales_rep"
        and lead.assigned_to_user_id not in {None, current_user.id}
    ):
        raise NotFoundError("Lead not found")
