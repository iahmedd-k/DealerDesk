import csv
from io import StringIO
import math
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApplicationError, BadRequestError, PayloadTooLargeError
from app.core.limiter import limiter
from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.models.quote import LeadQuote
from app.schemas.quotes import (
    LeadQuoteCreate,
    LeadQuoteResponse,
    LeadQuoteStatusUpdate,
)
from app.schemas.workspace import (
    BulkCustomerLeadUpdateRequest,
    CSVLeadImportRequest,
    CustomerLeadConvertRequest,
    CustomerLeadCreateRequest,
    CustomerLeadResponse,
    CustomerLeadUpdateRequest,
    LeadActivityCreateRequest,
    LeadActivityResponse,
)
from app.services import audit_service, lead_service, quote_service


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
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> CustomerLeadResponse:
    lead = lead_service.create_lead(
        db,
        dealership_id,
        payload,
        current_user,
        background_tasks=background_tasks,
    )
    audit_service.log_event(
        db,
        action="lead.created",
        resource_type="customer_lead",
        resource_id=str(lead.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={
            "source": lead.source,
            "consent_to_contact": lead.consent_to_contact,
            "channel_consents": {
                channel: getattr(lead, f"{channel}_consent")
                for channel in ("email", "sms", "whatsapp")
            },
        },
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
    overdue_only: bool = Query(default=False),
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
        overdue_only=overdue_only,
    )
    total = lead_service.count_leads(
        db,
        dealership_id,
        current_user,
        status=lead_status,
        overdue_only=overdue_only,
    )
    resolved_page_size = effective_limit
    resolved_page = page if page is not None else (effective_offset // resolved_page_size) + 1
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(resolved_page)
    response.headers["X-Page-Size"] = str(resolved_page_size)
    response.headers["X-Total-Pages"] = str(math.ceil(total / resolved_page_size) if resolved_page_size > 0 else 1)
    return [CustomerLeadResponse.model_validate(lead) for lead in leads]


@router.post("/bulk", response_model=list[CustomerLeadResponse])
def bulk_update_leads(
    dealership_id: int,
    payload: BulkCustomerLeadUpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> list[CustomerLeadResponse]:
    leads = lead_service.bulk_update_leads(
        db,
        dealership_id,
        current_user,
        payload,
        background_tasks=background_tasks,
    )
    audit_service.log_event(
        db,
        action="lead.bulk_updated",
        resource_type="customer_lead",
        resource_id=",".join(str(lead.id) for lead in leads),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={
            "lead_count": len(leads),
            "fields": sorted(payload.model_fields_set - {"lead_ids"}),
        },
    )
    return [CustomerLeadResponse.model_validate(lead) for lead in leads]


@router.post("/import")
def import_leads_from_csv(
    dealership_id: int,
    payload: CSVLeadImportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        reader = csv.DictReader(StringIO(payload.csv_content))
        headers = {
            str(header).strip().lower()
            for header in (reader.fieldnames or [])
            if header is not None
        }
        required_headers = {"name", "email", "message", "consent_to_contact"}
        if not required_headers.issubset(headers):
            raise BadRequestError(
                "CSV headers must include name, email, message, and consent_to_contact"
            )
        rows = list(reader)
    except csv.Error as exc:
        raise BadRequestError("CSV content could not be parsed") from exc
    if not rows:
        raise BadRequestError("CSV must contain at least one lead row")
    if len(rows) > 500:
        raise PayloadTooLargeError("CSV imports are limited to 500 leads per request")

    created = 0
    errors: list[dict[str, object]] = []
    for row_number, raw_row in enumerate(rows, start=2):
        row = {
            str(key).strip().lower(): (value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        if row.get("consent_to_contact", "").lower() not in {"true", "yes", "1"}:
            errors.append(
                {"row": row_number, "error": "Contact consent must be explicitly true"}
            )
            continue
        channel_consents: dict[str, bool] = {}
        invalid_channel_consent = False
        for channel in ("email", "sms", "whatsapp"):
            field = f"{channel}_consent"
            value = row.get(field, "").lower()
            if value not in {"", "true", "yes", "1", "false", "no", "0"}:
                errors.append(
                    {
                        "row": row_number,
                        "error": f"{field} must be true or false when provided",
                    }
                )
                invalid_channel_consent = True
                break
            channel_consents[field] = value in {"true", "yes", "1"}
        if invalid_channel_consent:
            continue
        lead_data: dict[str, object] = {
            "name": row.get("name", ""),
            "email": row.get("email", ""),
            "message": row.get("message", ""),
            "consent_to_contact": True,
            **channel_consents,
            "source": row.get("source") or "walk_in",
            "phone": row.get("phone") or None,
            "requested_vehicle_id": row.get("requested_vehicle_id") or None,
            "budget": row.get("budget") or None,
            "purchase_timeline": row.get("purchase_timeline") or None,
        }
        try:
            lead_payload = CustomerLeadCreateRequest.model_validate(lead_data)
        except ValidationError as exc:
            errors.append(
                {"row": row_number, "error": exc.errors()[0]["msg"]}
            )
            continue
        try:
            lead = lead_service.create_lead(
                db,
                dealership_id,
                lead_payload,
                current_user,
                background_tasks=background_tasks,
            )
        except ApplicationError as exc:
            errors.append({"row": row_number, "error": exc.detail})
            continue
        audit_service.log_event(
            db,
            action="lead.created",
            resource_type="customer_lead",
            resource_id=str(lead.id),
            dealership_id=dealership_id,
            actor=current_user,
            ip_address=request.client.host if request.client else None,
            details={"source": lead.source, "imported": True},
        )
        created += 1

    return {"created": created, "failed": len(errors), "errors": errors}


@router.get("/export")
def export_leads_to_csv(
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
    overdue_only: bool = Query(default=False),
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> Response:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "name",
            "email",
            "phone",
            "message",
            "source",
            "status",
            "lost_reason",
            "email_consent",
            "email_consented_at",
            "email_opted_out_at",
            "sms_consent",
            "sms_consented_at",
            "sms_opted_out_at",
            "whatsapp_consent",
            "whatsapp_consented_at",
            "whatsapp_opted_out_at",
            "assigned_to_user_id",
            "next_follow_up_at",
            "budget",
            "purchase_timeline",
            "deal_value",
            "deal_notes",
            "trade_in_vehicle",
            "trade_in_value",
            "down_payment",
            "apr_percent",
            "loan_term_months",
        ]
    )
    offset = 0
    exported = 0
    while True:
        page = lead_service.list_leads(
            db,
            dealership_id,
            current_user,
            status=lead_status,
            limit=500,
            offset=offset,
            overdue_only=overdue_only,
        )
        for lead in page:
            writer.writerow(
                [
                    lead.id,
                    lead.name,
                    lead.email,
                    lead.phone or "",
                    lead.message,
                    lead.source,
                    lead.status,
                    lead.lost_reason or "",
                    lead.email_consent,
                    lead.email_consented_at.isoformat()
                    if lead.email_consented_at
                    else "",
                    lead.email_opted_out_at.isoformat()
                    if lead.email_opted_out_at
                    else "",
                    lead.sms_consent,
                    lead.sms_consented_at.isoformat()
                    if lead.sms_consented_at
                    else "",
                    lead.sms_opted_out_at.isoformat()
                    if lead.sms_opted_out_at
                    else "",
                    lead.whatsapp_consent,
                    lead.whatsapp_consented_at.isoformat()
                    if lead.whatsapp_consented_at
                    else "",
                    lead.whatsapp_opted_out_at.isoformat()
                    if lead.whatsapp_opted_out_at
                    else "",
                    lead.assigned_to_user_id or "",
                    lead.next_follow_up_at.isoformat()
                    if lead.next_follow_up_at
                    else "",
                    lead.budget if lead.budget is not None else "",
                    lead.purchase_timeline or "",
                    lead.deal_value if lead.deal_value is not None else "",
                    lead.deal_notes or "",
                    lead.trade_in_vehicle or "",
                    lead.trade_in_value if lead.trade_in_value is not None else "",
                    lead.down_payment if lead.down_payment is not None else "",
                    lead.apr_percent if lead.apr_percent is not None else "",
                    lead.loan_term_months if lead.loan_term_months is not None else "",
                ]
            )
        exported += len(page)
        if exported > 20000:
            raise PayloadTooLargeError("Export is limited to 20,000 leads per request")
        if len(page) < 500:
            break
        offset += len(page)
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="dealerdesk-leads.csv"'
        },
    )


@router.patch("/{lead_id}", response_model=CustomerLeadResponse)
def update_lead(
    dealership_id: int,
    lead_id: int,
    payload: CustomerLeadUpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerLeadResponse:
    lead = lead_service.update_lead(
        db,
        dealership_id,
        lead_id,
        current_user,
        payload,
        background_tasks=background_tasks,
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> CustomerLeadResponse:
    lead = lead_service.auto_assign_lead(
        db, dealership_id, lead_id, current_user, background_tasks=background_tasks
    )
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


@router.get("/{lead_id}/quotes", response_model=list[LeadQuoteResponse])
def list_lead_quotes(
    dealership_id: int,
    lead_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[LeadQuote]:
    return quote_service.list_quotes(db, dealership_id, lead_id, current_user)


@router.post(
    "/{lead_id}/quotes",
    response_model=LeadQuoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lead_quote(
    dealership_id: int,
    lead_id: int,
    payload: LeadQuoteCreate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> LeadQuote:
    return quote_service.create_quote(
        db,
        dealership_id,
        lead_id,
        current_user,
        payload,
    )


@router.patch(
    "/{lead_id}/quotes/{quote_id}",
    response_model=LeadQuoteResponse,
)
def update_lead_quote_status(
    dealership_id: int,
    lead_id: int,
    quote_id: int,
    payload: LeadQuoteStatusUpdate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> LeadQuote:
    return quote_service.update_quote_status(
        db,
        dealership_id,
        lead_id,
        quote_id,
        current_user,
        payload,
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
