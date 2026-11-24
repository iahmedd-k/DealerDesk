from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.roles import STAFF_ROLES
from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.schemas.workspace import (
    CustomerLeadConvertRequest,
    CustomerLeadCreateRequest,
    CustomerLeadResponse,
    CustomerLeadUpdateRequest,
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
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[CustomerLeadResponse]:
    leads = lead_service.list_leads(
        db,
        dealership_id,
        current_user,
        status=lead_status,
        limit=limit,
        offset=offset,
    )
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
