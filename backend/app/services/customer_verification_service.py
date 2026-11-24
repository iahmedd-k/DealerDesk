from datetime import datetime, timezone
import logging
import re
import secrets
from typing import Any
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.roles import CUSTOMER_ROLE
from app.models.channel import TestDriveSlotHold
from app.models.user import User
from app.models.workspace import Dealership, TestDriveBooking, TestDriveSlot, Vehicle
from app.repositories import test_drive_repository, user_repository
from app.schemas.channel import (
    BookingVerificationConfirmRequest,
    BookingVerificationConfirmResponse,
    BookingVerificationInitiateRequest,
    BookingVerificationInitiateResponse,
)
from app.schemas.workspace import TestDriveBookingRequest
from app.services import (
    auth_service,
    conversation_service,
    dealership_service,
    otp_service,
    slot_hold_service,
    test_drive_service,
)

logger = logging.getLogger("dealerdesk.verification")


def _normalize_identifier(destination: str) -> str:
    cleaned = destination.strip().lower()
    if "@" in cleaned:
        return cleaned
    # Normalize phone: keep leading + if present, strip spaces/hyphens
    digits = re.sub(r"[^\d+]", "", cleaned)
    return digits or cleaned


def _resolve_or_create_customer(
    db: Session,
    dealership_id: int,
    identifier: str,
    customer_name: str | None = None,
) -> User:
    """
    Deterministically resolves an existing customer or JIT-provisions a new verified
    customer account with role CUSTOMER_ROLE.
    Never exposes to external callers whether an account existed previously.
    """
    clean_id = _normalize_identifier(identifier)
    
    if "@" in clean_id:
        existing = user_repository.get_by_email(db, clean_id)
        if existing:
            return existing
        user_email = clean_id
    else:
        # Phone identifier: map to synthetic email domain for unique User account
        phone_digits = re.sub(r"\D", "", clean_id)
        candidate_email = f"phone_{phone_digits}@customer.dealerdesk.local"
        existing = user_repository.get_by_email(db, candidate_email)
        if existing:
            return existing
        user_email = candidate_email

    # Provision verified customer account
    random_password = secrets.token_urlsafe(24)
    hashed_password = auth_service.hash_password(random_password)
    display_name = customer_name.strip() if customer_name and customer_name.strip() else "Valued Customer"

    new_user = user_repository.create(
        db,
        name=display_name,
        email=user_email,
        password=hashed_password,
        role=CUSTOMER_ROLE,
        dealership_id=dealership_id,
        commit=True,
    )
    new_user.is_email_verified = True
    db.commit()
    db.refresh(new_user)
    return new_user


def initiate_booking_verification(
    db: Session,
    dealership_id: int,
    payload: BookingVerificationInitiateRequest,
) -> BookingVerificationInitiateResponse:
    """
    Flow Steps 1-4, 8-9:
    - Verifies slot and vehicle availability.
    - Acquires a 10-minute hold on the slot.
    - Dispatches a single-use OTP to the customer's phone or email.
    - Does NOT reveal whether the identifier already has an account.
    """
    dealership = dealership_service.get_active_dealership(db, dealership_id)
    clean_dest = _normalize_identifier(payload.destination)

    # 1. Verify slot exists and belongs to dealership
    slot = test_drive_repository.get_slot(db, dealership_id, payload.slot_id)
    if slot is None:
        raise NotFoundError("Test-drive slot not found")

    if not slot.is_active:
        raise ConflictError("Test-drive slot is inactive")

    # 2. Acquire 10-minute slot hold lease
    hold = slot_hold_service.acquire_slot_hold(
        db,
        dealership_id=dealership_id,
        slot_id=payload.slot_id,
        identifier=clean_dest,
        duration_minutes=10,
    )

    # 3. Request OTP code (enforcing 60s cooldown and 3 attempts)
    raw_code, expires_at = otp_service.request_otp(
        db,
        dealership_id=dealership_id,
        channel=payload.channel,
        identifier=clean_dest,
        purpose="test_drive_booking",
    )

    # 4. If conversation_id is provided, log system message
    if payload.conversation_id:
        conversation_service.append_message(
            db,
            conversation_id=payload.conversation_id,
            sender_type="system",
            content=f"Verification OTP dispatched to {clean_dest} via {payload.channel}. Slot hold reserved.",
            channel_metadata={"hold_token": hold.hold_token, "slot_id": payload.slot_id},
        )

    masked_dest = clean_dest if "@" in clean_dest else (clean_dest[:3] + "****" + clean_dest[-3:] if len(clean_dest) > 6 else clean_dest)
    message = (
        f"A 6-digit verification code has been dispatched to {masked_dest}. "
        f"Your slot is temporarily reserved for 10 minutes. "
        f"Please provide the 6-digit code and confirmation to complete your booking."
    )

    return BookingVerificationInitiateResponse(
        status="otp_sent",
        hold_token=hold.hold_token,
        slot_id=payload.slot_id,
        destination=clean_dest,
        channel=payload.channel,
        expires_at=expires_at.isoformat(),
        message=message,
    )


def verify_customer_and_confirm_booking(
    db: Session,
    dealership_id: int,
    payload: BookingVerificationConfirmRequest,
) -> BookingVerificationConfirmResponse:
    """
    Flow Steps 4-7, 10-12:
    - Enforces explicit customer confirmation.
    - Cryptographically verifies single-use OTP (with attempt limits & expiry).
    - Checks and validates the active slot hold.
    - Deterministically resolves or JIT creates the customer account.
    - Creates the booking with backend concurrency locks.
    - Confirms the hold token.
    - Links conversation session to customer.
    - Dispatches confirmation message through channel.
    """
    if not payload.confirmed:
        raise BadRequestError("Explicit customer confirmation is required to book a test drive.")

    clean_dest = _normalize_identifier(payload.destination)

    # 1. Verify OTP with constant-time check & attempt limits
    otp_service.verify_otp(
        db,
        dealership_id=dealership_id,
        identifier=clean_dest,
        code=payload.code,
        purpose="test_drive_booking",
    )

    # 2. Check active slot hold
    hold = slot_hold_service.get_active_slot_hold(db, payload.hold_token)
    if hold is None:
        raise ConflictError(
            "Your reservation hold has expired or is invalid. Please select an available slot to try again."
        )

    # 3. Resolve or JIT-provision customer account (opaque to client)
    customer_user = _resolve_or_create_customer(
        db,
        dealership_id=dealership_id,
        identifier=clean_dest,
        customer_name=payload.customer_name,
    )

    # 4. Atomic booking execution using existing test_drive_service
    booking_req = TestDriveBookingRequest(
        confirmed=True,
        hold_token=payload.hold_token,
    )

    booking = test_drive_service.book_slot(
        db=db,
        dealership_id=dealership_id,
        slot_id=hold.slot_id,
        current_user=customer_user,
        payload=booking_req,
    )

    # 5. Link conversation session to verified customer
    if payload.conversation_id:
        conversation_service.link_customer(
            db,
            conversation_id=payload.conversation_id,
            customer_id=customer_user.id,
        )

    # 6. Retrieve vehicle details for confirmation response
    slot = test_drive_repository.get_slot(db, dealership_id, booking.slot_id)
    vehicle = test_drive_repository.get_vehicle(db, booking.vehicle_id)
    vehicle_name = f"{vehicle.model_year} {vehicle.make} {vehicle.model}" if vehicle else "Vehicle"

    starts_dt = slot.starts_at if slot else datetime.now(timezone.utc)
    ends_dt = slot.ends_at if slot else starts_dt
    starts_str = starts_dt.strftime("%A, %B %d, %Y at %I:%M %p")

    confirmation_msg = (
        f"Your test drive for the {vehicle_name} is officially confirmed! "
        f"Date: {starts_str}. "
        f"Booking Reference: #{booking.id}. "
        f"A confirmation receipt has been sent to {clean_dest}."
    )

    if payload.conversation_id:
        conversation_service.append_message(
            db,
            conversation_id=payload.conversation_id,
            sender_type="agent",
            content=confirmation_msg,
            channel_metadata={"booking_id": booking.id, "slot_id": booking.slot_id},
        )

    return BookingVerificationConfirmResponse(
        status="confirmed",
        booking_id=booking.id,
        customer_id=customer_user.id,
        slot_id=booking.slot_id,
        vehicle_id=booking.vehicle_id,
        vehicle_name=vehicle_name,
        starts_at=starts_dt.isoformat(),
        ends_at=ends_dt.isoformat(),
        message=confirmation_msg,
    )
