from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
from typing import Any
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.workspace import CustomerLead, TestDriveSlot, Vehicle
from app.repositories import lead_repository, test_drive_repository, vehicle_repository
from app.schemas.channel import (
    BookingVerificationConfirmRequest,
    BookingVerificationInitiateRequest,
)
from app.schemas.knowledge import KnowledgeSearchRequest
from app.services import customer_verification_service, knowledge_service, slot_hold_service


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def search_inventory(
    db: Session,
    dealership_id: int,
    *,
    query: str | None = None,
    make: str | None = None,
    model: str | None = None,
    min_price: Decimal | float | None = None,
    max_price: Decimal | float | None = None,
    min_year: int | None = None,
    brand_id: int | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Finds available vehicles in the dealership catalog matching customer criteria.
    """
    vehicles = vehicle_repository.list_for_dealership(
        db,
        dealership_id,
        brand_id=brand_id,
        include_archived_brands=False,
    )

    search_terms: list[str] = []
    if query:
        words = [w.strip() for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", query.lower())]
        stop_words = {
            "looking", "for", "reliable", "hello", "need", "want", "find",
            "have", "with", "under", "below", "cars", "car", "vehicle", "vehicles",
            "what", "show", "some", "good", "best", "available", "stock", "inventory",
            "you", "your", "the", "any", "all", "please", "models", "options"
        }
        search_terms = [w for w in words if w not in stop_words and not w.isdigit()]

    results: list[Vehicle] = []
    for v in vehicles:
        if not v.is_available:
            continue
        if make and make.lower() not in v.make.lower():
            continue
        if model and model.lower() not in v.model.lower():
            continue
        if min_year and v.model_year < min_year:
            continue
        if min_price and v.price < Decimal(str(min_price)):
            continue
        if max_price and v.price > Decimal(str(max_price)):
            continue
        if search_terms:
            match = any(
                term in v.make.lower()
                or term in v.model.lower()
                or (v.variant and term in v.variant.lower())
                or (v.description and term in v.description.lower())
                for term in search_terms
            )
            if not match:
                continue
        results.append(v)

    matched = results[:limit]
    return [
        {
            "id": v.id,
            "brand_id": v.brand_id,
            "make": v.make,
            "model": v.model,
            "model_year": v.model_year,
            "variant": v.variant,
            "price": float(v.price),
            "stock_number": v.stock_number,
            "test_drive_enabled": v.test_drive_enabled,
            "primary_image_url": v.images[0].public_url if v.images else None,
            "description": v.description,
        }
        for v in matched
    ]


def get_vehicle_details(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
) -> dict[str, Any] | None:
    """
    Retrieves full details for a specific vehicle including all photos and specifications.
    """
    vehicle = vehicle_repository.get_for_dealership(db, dealership_id, vehicle_id)
    if vehicle is None or not vehicle.is_available:
        return None

    return {
        "id": vehicle.id,
        "brand_id": vehicle.brand_id,
        "make": vehicle.make,
        "model": vehicle.model,
        "model_year": vehicle.model_year,
        "variant": vehicle.variant,
        "price": float(vehicle.price),
        "stock_number": vehicle.stock_number,
        "test_drive_enabled": vehicle.test_drive_enabled,
        "description": vehicle.description,
        "images": [
            {
                "url": img.public_url,
                "alt_text": img.alt_text,
                "position": img.position,
            }
            for img in vehicle.images
        ],
    }


def compare_vehicles(
    db: Session,
    dealership_id: int,
    vehicle_ids: list[int],
) -> dict[str, Any]:
    """
    Generates a side-by-side comparison for 2 to 3 vehicles.
    """
    items = []
    for vid in vehicle_ids[:3]:
        details = get_vehicle_details(db, dealership_id, vid)
        if details:
            items.append(details)

    if not items:
        return {"comparison": [], "summary": "No matching vehicles found for comparison."}

    summary = (
        f"Comparing {len(items)} vehicles: "
        + ", ".join(f"{v['model_year']} {v['make']} {v['model']} (${v['price']:,.2f})" for v in items)
    )
    return {
        "vehicles": items,
        "summary": summary,
    }


def get_available_test_drive_slots(
    db: Session,
    dealership_id: int,
    *,
    vehicle_id: int | None = None,
    days_ahead: int = 7,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Retrieves upcoming available test-drive slots, accounting for both booked slots and active temporary holds.
    """
    raw_slots = test_drive_repository.list_slots(
        db,
        dealership_id,
        vehicle_id=vehicle_id,
        available_only=True,
    )

    now = datetime.now(timezone.utc)
    max_date = now + timedelta(days=days_ahead)

    available = []
    for s in raw_slots:
        if not s.is_active:
            continue
        starts_utc = _utc(s.starts_at)
        if starts_utc <= now or starts_utc > max_date:
            continue

        active_holds = slot_hold_service.get_active_holds_count_for_slot(db, s.id)
        remaining_capacity = s.capacity - s.booked_count - active_holds
        if remaining_capacity > 0:
            available.append(
                {
                    "id": s.id,
                    "vehicle_id": s.vehicle_id,
                    "starts_at": starts_utc.isoformat(),
                    "ends_at": _utc(s.ends_at).isoformat(),
                    "remaining_capacity": remaining_capacity,
                }
            )

    return available[:limit]


def request_test_drive_hold(
    db: Session,
    dealership_id: int,
    slot_id: int,
    identifier: str,
    customer_id: int | None = None,
) -> dict[str, Any]:
    """
    Places a temporary 10-minute hold on a slot while awaiting customer OTP verification.
    """
    hold = slot_hold_service.acquire_slot_hold(
        db,
        dealership_id=dealership_id,
        slot_id=slot_id,
        identifier=identifier,
        customer_id=customer_id,
        duration_minutes=10,
    )
    return {
        "hold_token": hold.hold_token,
        "slot_id": hold.slot_id,
        "identifier": hold.identifier,
        "expires_at": hold.expires_at.isoformat(),
        "status": hold.status,
    }


def create_customer_lead(
    db: Session,
    dealership_id: int,
    *,
    name: str,
    email: str,
    phone: str | None = None,
    requested_vehicle_id: int | None = None,
    message: str = "",
    source: str = "sales_agent",
) -> dict[str, Any]:
    """
    Captures an interested customer as a verified CRM lead.
    """
    now = datetime.now(timezone.utc)
    lead = CustomerLead(
        dealership_id=dealership_id,
        name=name.strip(),
        email=email.strip().lower(),
        phone=phone.strip() if phone else None,
        requested_vehicle_id=requested_vehicle_id,
        message=message or "Expressed purchase interest via Sales Agent.",
        source=source,
        status="new",
        consent_to_contact=True,
        consented_at=now,
        created_at=now,
        updated_at=now,
    )
    saved = lead_repository.save(db, lead)
    from app.services import lead_service
    lead_service.notify_new_lead(db, dealership_id, saved)
    return {
        "id": saved.id,
        "dealership_id": saved.dealership_id,
        "name": saved.name,
        "email": saved.email,
        "status": saved.status,
        "created_at": saved.created_at.isoformat(),
    }


def search_public_knowledge(
    db: Session,
    dealership_id: int,
    query: str,
    brand_id: int | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Retrieves public dealership information, warranties, financing FAQ, and policies via vector RAG.
    """
    results = knowledge_service.search(
        db,
        dealership_id,
        KnowledgeSearchRequest(
            query=query,
            brand_id=brand_id,
            limit=limit,
        ),
    )
    return [
        {
            "document_id": r.document_id,
            "filename": r.filename,
            "page_number": r.page_number,
            "snippet": r.content,
            "score": r.score,
        }
        for r in results
    ]


def initiate_booking_verification(
    db: Session,
    dealership_id: int,
    slot_id: int,
    destination: str,
    channel: str = "website",
    customer_name: str | None = None,
    conversation_id: int | None = None,
) -> dict[str, Any]:
    """
    Triggers slot reservation hold and single-use OTP generation for test-drive booking.
    """
    res = customer_verification_service.initiate_booking_verification(
        db,
        dealership_id=dealership_id,
        payload=BookingVerificationInitiateRequest(
            slot_id=slot_id,
            destination=destination,
            channel=channel,
            customer_name=customer_name,
            conversation_id=conversation_id,
        ),
    )
    return res.model_dump()


def confirm_booking_with_otp(
    db: Session,
    dealership_id: int,
    hold_token: str,
    code: str,
    destination: str,
    channel: str = "website",
    customer_name: str | None = None,
    notes: str | None = None,
    confirmed: bool = True,
    conversation_id: int | None = None,
) -> dict[str, Any]:
    """
    Verifies single-use OTP and creates confirmed test-drive booking.
    """
    res = customer_verification_service.verify_customer_and_confirm_booking(
        db,
        dealership_id=dealership_id,
        payload=BookingVerificationConfirmRequest(
            hold_token=hold_token,
            code=code,
            destination=destination,
            channel=channel,
            customer_name=customer_name,
            notes=notes,
            confirmed=confirmed,
            conversation_id=conversation_id,
        ),
    )
    return res.model_dump()

