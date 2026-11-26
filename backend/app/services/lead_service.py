from datetime import datetime, timezone
import logging

from fastapi import BackgroundTasks
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
from app.core.roles import CUSTOMER_ROLE, DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.models.user import User
from app.models.workspace import CustomerLead, LeadActivity
from app.repositories import dealership_repository, lead_repository
from app.schemas.workspace import (
    CustomerLeadCreateRequest,
    CustomerLeadUpdateRequest,
    LeadActivityCreateRequest,
    VehicleStatusTransitionRequest,
)
from app.services import assistant_service, email_service, outbox_service, vehicle_service

logger = logging.getLogger(__name__)


def create_lead(
    db: Session,
    dealership_id: int,
    payload: CustomerLeadCreateRequest,
    current_user: User | None,
    background_tasks: BackgroundTasks | None = None,
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
    auto_rep = (
        lead_repository.find_least_loaded_sales_rep(db, dealership_id)
        if getattr(payload, "auto_assign", False)
        else None
    )
    lead = CustomerLead(
        dealership_id=dealership_id,
        customer_id=(
            current_user.id
            if current_user is not None and current_user.role == CUSTOMER_ROLE
            else None
        ),
        requested_vehicle_id=vehicle_id,
        assigned_to_user_id=auto_rep.id if auto_rep is not None else None,
        name=payload.name,
        email=str(payload.email).lower(),
        phone=payload.phone,
        message=payload.message,
        source=payload.source,
        budget=getattr(payload, "budget", None),
        purchase_timeline=getattr(payload, "purchase_timeline", None),
        conversation_id=getattr(payload, "conversation_id", None),
        preferences=getattr(payload, "preferences", None),
        consent_to_contact=True,
        consented_at=now,
        created_at=now,
        updated_at=now,
    )
    saved = lead_repository.save(db, lead)
    _record_activity(
        db,
        dealership_id=dealership_id,
        lead_id=saved.id,
        actor_user_id=current_user.id if current_user is not None else None,
        activity_type="created",
        summary=f"Lead captured via {saved.source}",
        details={
            "source": saved.source,
            "budget": float(saved.budget) if saved.budget is not None else None,
            "purchase_timeline": saved.purchase_timeline,
            "conversation_id": saved.conversation_id,
        },
    )
    if auto_rep is not None:
        _record_activity(
            db,
            dealership_id=dealership_id,
            lead_id=saved.id,
            actor_user_id=None,
            activity_type="assigned",
            summary=f"Auto-assigned to {auto_rep.name} (round-robin)",
            details={"assigned_to_user_id": auto_rep.id, "mode": "auto"},
        )
        _notify_lead_assigned(db, dealership_id, saved, background_tasks=background_tasks)

    notify_new_lead(db, dealership_id, saved, background_tasks=background_tasks)
    try:
        outbox_service.enqueue_event(
            db,
            dealership_id=dealership_id,
            event_type="lead.created",
            aggregate_type="customer_lead",
            aggregate_id=saved.id,
            payload={"lead_id": saved.id, "source": saved.source, "status": saved.status},
        )
    except Exception as exc:
        logger.warning("Outbox enqueue failed for lead.created %s: %s", saved.id, exc)
    return saved


def count_leads(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    status: str | None,
) -> int:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    return lead_repository.count_leads(
        db,
        dealership_id,
        status=status,
        sales_rep_user_id=(
            current_user.id if current_user.role == "sales_rep" else None
        ),
    )


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
    background_tasks: BackgroundTasks | None = None,
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
        requested_status = changes["status"]
        if requested_status not in {"test_drive_scheduled", "follow_up", "won", "lost"}:
            raise ConflictError(
                "A lead linked to a booking can only transition to 'follow_up', 'won', or 'lost'"
            )
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

    is_marking_won = changes.get("status") == "won" and lead.status != "won"
    target_vehicle_id = lead.requested_vehicle_id
    linked_booking = None
    if lead.test_drive_booking_id is not None:
        linked_booking = lead_repository.get_booking(
            db, dealership_id, lead.test_drive_booking_id
        )
        if target_vehicle_id is None and linked_booking is not None:
            target_vehicle_id = linked_booking.vehicle_id

    if is_marking_won and target_vehicle_id is not None:
        target_vehicle = lead_repository.get_vehicle(db, dealership_id, target_vehicle_id)
        if target_vehicle is not None and target_vehicle.status == "sold":
            raise ConflictError("This vehicle has already been sold")

    previous_status = lead.status
    previous_assignee_id = lead.assigned_to_user_id
    previous_follow_up = lead.next_follow_up_at
    previous_deal_value = getattr(lead, "deal_value", None)
    previous_deal_notes = getattr(lead, "deal_notes", None)

    for field, value in changes.items():
        setattr(lead, field, value)
    if lead.status in {"lost", "won"}:
        lead.next_follow_up_at = None
    lead.updated_at = datetime.now(timezone.utc)

    if is_marking_won and linked_booking is not None and linked_booking.status == "booked":
        linked_booking.status = "completed"
        db.add(linked_booking)

    saved = lead_repository.save(db, lead)

    if saved.status != previous_status:
        _record_activity(
            db,
            dealership_id=dealership_id,
            lead_id=saved.id,
            actor_user_id=current_user.id,
            activity_type="status_changed",
            summary=f"Status changed from '{previous_status}' to '{saved.status}'",
            details={"previous_status": previous_status, "new_status": saved.status},
        )
    if "assigned_to_user_id" in changes and saved.assigned_to_user_id != previous_assignee_id:
        _record_activity(
            db,
            dealership_id=dealership_id,
            lead_id=saved.id,
            actor_user_id=current_user.id,
            activity_type="assigned",
            summary=(
                f"Assigned to staff user #{saved.assigned_to_user_id}"
                if saved.assigned_to_user_id is not None
                else "Lead unassigned"
            ),
            details={"assigned_to_user_id": saved.assigned_to_user_id},
        )
    if (
        "next_follow_up_at" in changes
        and saved.next_follow_up_at is not None
        and saved.next_follow_up_at != previous_follow_up
    ):
        _record_activity(
            db,
            dealership_id=dealership_id,
            lead_id=saved.id,
            actor_user_id=current_user.id,
            activity_type="follow_up_scheduled",
            summary=f"Follow-up scheduled for {saved.next_follow_up_at.isoformat()}",
        )
    if (
        ("deal_value" in changes and getattr(saved, "deal_value", None) != previous_deal_value)
        or ("deal_notes" in changes and getattr(saved, "deal_notes", None) != previous_deal_notes)
    ):
        deal_val = getattr(saved, "deal_value", None)
        _record_activity(
            db,
            dealership_id=dealership_id,
            lead_id=saved.id,
            actor_user_id=current_user.id,
            activity_type="deal_updated",
            summary="Deal details updated",
            details={
                "deal_value": float(deal_val) if deal_val is not None else None,
                "deal_notes": getattr(saved, "deal_notes", None),
            },
        )

    if is_marking_won and target_vehicle_id is not None:
        vehicle_service.transition_vehicle_status(
            db,
            dealership_id,
            target_vehicle_id,
            current_user,
            VehicleStatusTransitionRequest(
                status="sold",
                notes=f"Sold via Lead #{saved.id} ({saved.name})",
            ),
        )
    if is_marking_won:
        try:
            outbox_service.enqueue_event(
                db,
                dealership_id=dealership_id,
                event_type="lead.won",
                aggregate_type="customer_lead",
                aggregate_id=saved.id,
                payload={
                    "lead_id": saved.id,
                    "vehicle_id": target_vehicle_id,
                    "deal_value": float(getattr(saved, "deal_value", 0) or 0),
                },
            )
        except Exception as exc:
            logger.warning("Outbox enqueue failed for lead.won %s: %s", saved.id, exc)

    if (
        "assigned_to_user_id" in changes
        and saved.assigned_to_user_id is not None
        and saved.assigned_to_user_id != previous_assignee_id
    ):
        _notify_lead_assigned(db, dealership_id, saved, background_tasks=background_tasks)

    return saved


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
        saved = lead_repository.save(db, lead)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("This test-drive booking is already linked to a lead") from exc

    _record_activity(
        db,
        dealership_id=dealership_id,
        lead_id=saved.id,
        actor_user_id=current_user.id,
        activity_type="booking_linked",
        summary=f"Linked to test-drive booking #{booking.id}",
        details={"test_drive_booking_id": booking.id},
    )
    return saved


def auto_assign_lead(
    db: Session,
    dealership_id: int,
    lead_id: int,
    current_user: User,
    background_tasks: BackgroundTasks | None = None,
) -> CustomerLead:
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    lead = lead_repository.get_lead(db, dealership_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    rep = lead_repository.find_least_loaded_sales_rep(db, dealership_id)
    if rep is None:
        raise ConflictError("No active dealership staff available for auto-assignment")
    lead.assigned_to_user_id = rep.id
    lead.updated_at = datetime.now(timezone.utc)
    saved = lead_repository.save(db, lead)
    _record_activity(
        db,
        dealership_id=dealership_id,
        lead_id=saved.id,
        actor_user_id=current_user.id,
        activity_type="assigned",
        summary=f"Auto-assigned to {rep.name} (round-robin)",
        details={"assigned_to_user_id": rep.id, "mode": "auto"},
    )
    _notify_lead_assigned(db, dealership_id, saved, background_tasks=background_tasks)
    return saved


def list_lead_activities(
    db: Session,
    dealership_id: int,
    lead_id: int,
    current_user: User,
) -> list[LeadActivity]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    lead = lead_repository.get_lead(db, dealership_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    _ensure_lead_visibility(lead, current_user)
    return lead_repository.list_activities(db, dealership_id, lead_id)


def add_lead_activity(
    db: Session,
    dealership_id: int,
    lead_id: int,
    current_user: User,
    payload: LeadActivityCreateRequest,
) -> LeadActivity:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    lead = lead_repository.get_lead(db, dealership_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    _ensure_lead_visibility(lead, current_user)
    activity = LeadActivity(
        dealership_id=dealership_id,
        lead_id=lead_id,
        actor_user_id=current_user.id,
        activity_type=payload.activity_type,
        summary=payload.summary.strip(),
        details=payload.details,
        created_at=datetime.now(timezone.utc),
    )
    return lead_repository.save_activity(db, activity)


def delete_lead(
    db: Session,
    dealership_id: int,
    lead_id: int,
    current_user: User,
) -> None:
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    lead = lead_repository.get_lead(db, dealership_id, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    lead_repository.delete_lead(db, lead)


def _record_activity(
    db: Session,
    *,
    dealership_id: int,
    lead_id: int,
    actor_user_id: int | None,
    activity_type: str,
    summary: str,
    details: dict | None = None,
) -> None:
    try:
        lead_repository.save_activity(
            db,
            LeadActivity(
                dealership_id=dealership_id,
                lead_id=lead_id,
                actor_user_id=actor_user_id,
                activity_type=activity_type,
                summary=summary,
                details=details,
                created_at=datetime.now(timezone.utc),
            ),
        )
    except Exception as exc:
        logger.warning("Failed to record lead activity for lead %s: %s", lead_id, exc)


def _ensure_lead_visibility(lead: CustomerLead, current_user: User) -> None:
    if (
        current_user.role == "sales_rep"
        and lead.assigned_to_user_id not in {None, current_user.id}
    ):
        raise NotFoundError("Lead not found")


def _resolve_vehicle_label(
    db: Session,
    dealership_id: int,
    vehicle_id: int | None,
) -> str | None:
    if vehicle_id is None:
        return None
    vehicle = lead_repository.get_vehicle(db, dealership_id, vehicle_id)
    if vehicle is None:
        return None
    return f"{vehicle.model_year} {vehicle.make} {vehicle.model}"


def _send_new_lead_emails_task(
    *,
    lead_id: int,
    customer_email: str,
    customer_name: str,
    dealership_name: str,
    dealership_email: str | None,
    dealership_phone: str | None,
    vehicle_label: str | None,
    source: str,
    lead_phone: str | None,
    message: str,
) -> None:
    try:
        email_service.send_lead_acknowledgment(
            recipient=customer_email,
            customer_name=customer_name,
            dealership_name=dealership_name,
            dealership_phone=dealership_phone,
            vehicle_label=vehicle_label,
        )
        if dealership_email:
            email_service.send_new_lead_alert(
                recipient=dealership_email,
                dealership_name=dealership_name,
                lead_name=customer_name,
                lead_email=customer_email,
                lead_phone=lead_phone,
                source=source,
                vehicle_label=vehicle_label,
                message=message,
            )
    except Exception as exc:
        logger.warning("New lead email notification failed for lead %s: %s", lead_id, exc)


def _send_assigned_lead_email_task(
    *,
    lead_id: int,
    staff_email: str,
    staff_name: str,
    dealership_name: str,
    lead_name: str,
    lead_email: str,
    lead_phone: str | None,
    vehicle_label: str | None,
    message: str,
) -> None:
    try:
        email_service.send_lead_assigned_notification(
            recipient=staff_email,
            staff_name=staff_name,
            dealership_name=dealership_name,
            lead_name=lead_name,
            lead_email=lead_email,
            lead_phone=lead_phone,
            vehicle_label=vehicle_label,
            message=message,
            lead_id=lead_id,
        )
    except Exception as exc:
        logger.warning("Lead assignment email failed for lead %s: %s", lead_id, exc)


def notify_new_lead(
    db: Session,
    dealership_id: int,
    lead: CustomerLead,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Send acknowledgment to the customer and a new-lead alert to the dealership."""
    try:
        dealership = dealership_repository.get_by_id(db, dealership_id)
        if dealership is None:
            return
        vehicle_label = _resolve_vehicle_label(db, dealership_id, lead.requested_vehicle_id)
        kwargs = {
            "lead_id": lead.id,
            "customer_email": lead.email,
            "customer_name": lead.name,
            "dealership_name": dealership.name,
            "dealership_email": dealership.email,
            "dealership_phone": dealership.phone,
            "vehicle_label": vehicle_label,
            "source": lead.source,
            "lead_phone": lead.phone,
            "message": lead.message,
        }
        if background_tasks is not None:
            background_tasks.add_task(_send_new_lead_emails_task, **kwargs)
        else:
            _send_new_lead_emails_task(**kwargs)
    except Exception as exc:
        logger.warning("New lead email notification failed for lead %s: %s", lead.id, exc)


def _notify_lead_assigned(
    db: Session,
    dealership_id: int,
    lead: CustomerLead,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    try:
        if lead.assigned_to_user_id is None:
            return
        staff_user = lead_repository.get_staff_user(
            db, dealership_id, lead.assigned_to_user_id
        )
        dealership = dealership_repository.get_by_id(db, dealership_id)
        if staff_user is None or dealership is None:
            return
        vehicle_label = _resolve_vehicle_label(db, dealership_id, lead.requested_vehicle_id)
        kwargs = {
            "lead_id": lead.id,
            "staff_email": staff_user.email,
            "staff_name": staff_user.name,
            "dealership_name": dealership.name,
            "lead_name": lead.name,
            "lead_email": lead.email,
            "lead_phone": lead.phone,
            "vehicle_label": vehicle_label,
            "message": lead.message,
        }
        if background_tasks is not None:
            background_tasks.add_task(_send_assigned_lead_email_task, **kwargs)
        else:
            _send_assigned_lead_email_task(**kwargs)
    except Exception as exc:
        logger.warning("Lead assignment email failed for lead %s: %s", lead.id, exc)
