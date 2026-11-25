import math
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.schemas.workspace import (
    CustomerLeadConvertRequest,
    CustomerLeadCreateRequest,
    CustomerLeadResponse,
    CustomerLeadUpdateRequest,
    LeadActivityCreateRequest,
    LeadActivityResponse,
)
from app.services import audit_service, lead_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}/leads",
    tags=["Customer Leads"],
)


@limiter.limit(get_settings().assistant_rate_limit)
@router.post("", response_model=CustomerLeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead(
    dealership_id: int,
    payload: CustomerLeadCreateRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> CustomerLeadResponse:
    lead = lead_service.create_lead(db, dealership_id, payload, current_user)
    audit_service.log_event(
        db,
        action="lead.created",
        resource_type="customer_lead",
        resource_id=str(lead.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={"source": lead.source, "consent_to_contact": lead.consent_to_contact},
    )
    return CustomerLeadResponse.model_validate(lead)


@router.get("", response_model=list[CustomerLeadResponse])
def list_leads(
    dealership_id: int,
    response: Response,
    lead_status: Literal[
        "new",
        "contacted",
        "qualified",
        "test_drive_scheduled",
        "won",
        "lost",
        "follow_up",
    ]
    | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    page: int | None = Query(default=None, ge=1, description="Page number starting at 1"),
    page_size: int | None = Query(default=None, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[CustomerLeadResponse]:
    effective_limit = page_size if page is not None and page_size is not None else limit
    effective_offset = (page - 1) * page_size if page is not None and page_size is not None else offset
    leads = lead_service.list_leads(
        db,
        dealership_id,
        current_user,
        status=lead_status,
        limit=effective_limit,
        offset=effective_offset,
    )
    total = lead_service.count_leads(
        db,
        dealership_id,
        current_user,
        status=lead_status,
    )
    resolved_page_size = effective_limit
    resolved_page = page if page is not None else (effective_offset // resolved_page_size) + 1
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(resolved_page)
    response.headers["X-Page-Size"] = str(resolved_page_size)
    response.headers["X-Total-Pages"] = str(math.ceil(total / resolved_page_size) if resolved_page_size > 0 else 1)
    return [CustomerLeadResponse.model_validate(lead) for lead in leads]


@router.patch("/{lead_id}", response_model=CustomerLeadResponse)
def update_lead(
    dealership_id: int,
    lead_id: int,
    payload: CustomerLeadUpdateRequest,
    request: Request,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerLeadResponse:
    lead = lead_service.update_lead(
        db,
        dealership_id,
        lead_id,
        current_user,
        payload,
    )
    audit_service.log_event(
        db,
        action="lead.updated",
        resource_type="customer_lead",
        resource_id=str(lead.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={"fields": sorted(payload.model_fields_set)},
    )
    return CustomerLeadResponse.model_validate(lead)


@router.post("/{lead_id}/convert", response_model=CustomerLeadResponse)
def convert_lead(
    dealership_id: int,
    lead_id: int,
    payload: CustomerLeadConvertRequest,
    request: Request,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerLeadResponse:
    lead = lead_service.convert_lead_to_booking(
        db,
        dealership_id,
        lead_id,
        payload.booking_id,
        current_user,
    )
    audit_service.log_event(
        db,
        action="lead.converted",
        resource_type="customer_lead",
        resource_id=str(lead.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={"test_drive_booking_id": lead.test_drive_booking_id},
    )
    return CustomerLeadResponse.model_validate(lead)


@router.post("/{lead_id}/auto-assign", response_model=CustomerLeadResponse)
def auto_assign_lead(
    dealership_id: int,
    lead_id: int,
    request: Request,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> CustomerLeadResponse:
    lead = lead_service.auto_assign_lead(db, dealership_id, lead_id, current_user)
    audit_service.log_event(
        db,
        action="lead.auto_assigned",
        resource_type="customer_lead",
        resource_id=str(lead.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={"assigned_to_user_id": lead.assigned_to_user_id},
    )
    return CustomerLeadResponse.model_validate(lead)


@router.get("/{lead_id}/activities", response_model=list[LeadActivityResponse])
def list_lead_activities(
    dealership_id: int,
    lead_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[LeadActivityResponse]:
    activities = lead_service.list_lead_activities(db, dealership_id, lead_id, current_user)
    return [
        LeadActivityResponse(
            id=item.id,
            dealership_id=item.dealership_id,
            lead_id=item.lead_id,
            actor_user_id=item.actor_user_id,
            actor_user_email=item.actor_user.email if item.actor_user else None,
            activity_type=item.activity_type,
            summary=item.summary,
            details=item.details,
            created_at=item.created_at,
        )
        for item in activities
    ]


@router.post(
    "/{lead_id}/activities",
    response_model=LeadActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_lead_activity(
    dealership_id: int,
    lead_id: int,
    payload: LeadActivityCreateRequest,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> LeadActivityResponse:
    item = lead_service.add_lead_activity(db, dealership_id, lead_id, current_user, payload)
    return LeadActivityResponse(
        id=item.id,
        dealership_id=item.dealership_id,
        lead_id=item.lead_id,
        actor_user_id=item.actor_user_id,
        actor_user_email=current_user.email,
        activity_type=item.activity_type,
        summary=item.summary,
        details=item.details,
        created_at=item.created_at,
    )


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    dealership_id: int,
    lead_id: int,
    request: Request,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    lead_service.delete_lead(db, dealership_id, lead_id, current_user)
    audit_service.log_event(
        db,
        action="lead.deleted",
        resource_type="customer_lead",
        resource_id=str(lead_id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
    )
