from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_role_access
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.roles import STAFF_ROLES
from app.models.quote import LeadQuote
from app.models.user import User
from app.models.workspace import CustomerLead, LeadActivity, Vehicle
from app.schemas.quotes import LeadQuoteCreate, LeadQuoteStatusUpdate

_CENT = Decimal("0.01")
_QUOTE_DISCLAIMER = (
    "Estimate only; excludes taxes, title, registration, dealer fees, "
    "lender approval, and other charges."
)


def _get_lead(
    db: Session,
    dealership_id: int,
    lead_id: int,
    *,
    lock: bool = False,
) -> CustomerLead:
    query = select(CustomerLead).where(
        CustomerLead.id == lead_id,
        CustomerLead.dealership_id == dealership_id,
    )
    if lock:
        query = query.with_for_update()
    lead = db.scalar(query)
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


def _calculate_monthly_payment(
    amount_financed: Decimal,
    apr_percent: Decimal,
    term_months: int,
) -> Decimal:
    if amount_financed == 0:
        return Decimal("0.00")
    monthly_rate = apr_percent / Decimal("1200")
    if monthly_rate == 0:
        payment = amount_financed / term_months
    else:
        payment = amount_financed * monthly_rate / (
            Decimal("1") - (Decimal("1") + monthly_rate) ** (-term_months)
        )
    return payment.quantize(_CENT, rounding=ROUND_HALF_UP)


def list_quotes(
    db: Session,
    dealership_id: int,
    lead_id: int,
    current_user: User,
) -> list[LeadQuote]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    _get_lead(db, dealership_id, lead_id)
    return list(
        db.scalars(
            select(LeadQuote)
            .where(
                LeadQuote.dealership_id == dealership_id,
                LeadQuote.lead_id == lead_id,
            )
            .order_by(LeadQuote.version.desc())
        )
    )


def create_quote(
    db: Session,
    dealership_id: int,
    lead_id: int,
    current_user: User,
    payload: LeadQuoteCreate,
) -> LeadQuote:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    lead = _get_lead(db, dealership_id, lead_id, lock=True)
    if payload.vehicle_id is not None:
        vehicle = db.scalar(
            select(Vehicle).where(
                Vehicle.id == payload.vehicle_id,
                Vehicle.dealership_id == dealership_id,
            )
        )
        if vehicle is None:
            raise NotFoundError("Vehicle not found in this dealership")

    amount_financed = (
        payload.sale_price - payload.trade_in_value - payload.down_payment
    )
    if amount_financed < 0:
        raise BadRequestError("Trade-in value and down payment cannot exceed sale price")
    monthly_payment = _calculate_monthly_payment(
        amount_financed,
        payload.apr_percent,
        payload.loan_term_months,
    )
    version = (
        db.scalar(
            select(func.max(LeadQuote.version)).where(
                LeadQuote.dealership_id == dealership_id,
                LeadQuote.lead_id == lead_id,
            )
        )
        or 0
    ) + 1
    now = datetime.now(timezone.utc)
    quote = LeadQuote(
        dealership_id=dealership_id,
        lead_id=lead_id,
        version=version,
        status="draft",
        vehicle_id=payload.vehicle_id,
        vehicle_label=payload.vehicle_label,
        sale_price=payload.sale_price,
        trade_in_vehicle=payload.trade_in_vehicle,
        trade_in_value=payload.trade_in_value,
        down_payment=payload.down_payment,
        amount_financed=amount_financed.quantize(_CENT, rounding=ROUND_HALF_UP),
        apr_percent=payload.apr_percent,
        loan_term_months=payload.loan_term_months,
        estimated_monthly_payment=monthly_payment,
        disclaimer=_QUOTE_DISCLAIMER,
        notes=payload.notes,
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(quote)
    try:
        db.flush()
        db.add(
            LeadActivity(
                dealership_id=dealership_id,
                lead_id=lead.id,
                actor_user_id=current_user.id,
                activity_type="quote",
                summary=f"Quote version {version} saved",
                details={
                    "quote_id": quote.id,
                    "version": version,
                    "sale_price": float(quote.sale_price),
                    "trade_in_value": float(quote.trade_in_value),
                    "down_payment": float(quote.down_payment),
                    "amount_financed": float(quote.amount_financed),
                    "apr_percent": float(quote.apr_percent),
                    "loan_term_months": quote.loan_term_months,
                    "estimated_monthly_payment": float(
                        quote.estimated_monthly_payment
                    ),
                    "disclaimer": quote.disclaimer,
                },
                created_at=now,
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Quote version could not be saved; try again") from exc
    db.refresh(quote)
    return quote


def update_quote_status(
    db: Session,
    dealership_id: int,
    lead_id: int,
    quote_id: int,
    current_user: User,
    payload: LeadQuoteStatusUpdate,
) -> LeadQuote:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    lead = _get_lead(db, dealership_id, lead_id)
    quote = db.scalar(
        select(LeadQuote).where(
            LeadQuote.id == quote_id,
            LeadQuote.lead_id == lead.id,
            LeadQuote.dealership_id == dealership_id,
        ).with_for_update()
    )
    if quote is None:
        raise NotFoundError("Quote not found")
    if quote.status == payload.status:
        return quote
    allowed = {
        "draft": {"sent", "accepted", "declined", "expired"},
        "sent": {"accepted", "declined", "expired"},
    }
    if payload.status not in allowed.get(quote.status, set()):
        raise ConflictError("This quote status cannot be changed")
    previous_status = quote.status
    quote.status = payload.status
    quote.updated_at = datetime.now(timezone.utc)
    db.add(
        LeadActivity(
            dealership_id=dealership_id,
            lead_id=lead.id,
            actor_user_id=current_user.id,
            activity_type="quote_status_changed",
            summary=f"Quote version {quote.version} marked {quote.status}",
            details={
                "quote_id": quote.id,
                "version": quote.version,
                "previous_status": previous_status,
                "new_status": quote.status,
            },
            created_at=quote.updated_at,
        )
    )
    db.commit()
    db.refresh(quote)
    return quote
