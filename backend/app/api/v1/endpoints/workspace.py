import secrets
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_roles
from app.models.user import User
from app.models.workspace import (
    Dealership,
    StaffInvitation,
    TestDriveSettings,
    TestDriveSlot,
    Vehicle,
)
from app.repositories import user_repository
from app.schemas.user import UserResponse
from app.schemas.workspace import (
    ActivationRequest,
    DealershipRegistrationRequest,
    StaffInvitationRequest,
    StaffInvitationResponse,
    TestDriveSettingsRequest,
    TestDriveSettingsResponse,
    TestDriveSlotResponse,
    VehicleCreateRequest,
    VehicleResponse,
)
from app.services import auth_service
from app.services.email_service import send_staff_invitation


router = APIRouter(tags=["Workspace"])


@router.post(
    "/dealerships/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_dealership(
    payload: DealershipRegistrationRequest,
    db: Session = Depends(get_db),
) -> User:
    admin_email = str(payload.admin_email).lower()
    dealership_email = str(payload.dealership_email).lower()
    if user_repository.get_by_email(db, admin_email):
        raise HTTPException(status_code=409, detail="Admin email is already registered")

    dealership = Dealership(
        name=payload.dealership_name,
        email=dealership_email,
        phone=payload.dealership_phone,
        address=payload.dealership_address,
        timezone=payload.timezone,
    )
    db.add(dealership)
    db.flush()
    admin = user_repository.create(
        db,
        name=payload.admin_name,
        email=admin_email,
        password=auth_service.hash_password(payload.admin_password),
        role="dealership_admin",
        dealership_id=dealership.id,
        commit=False,
    )
    db.add(TestDriveSettings(dealership_id=dealership.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dealership registration conflicts with existing data") from exc
    db.refresh(admin)
    return admin


@router.post(
    "/dealerships/{dealership_id}/staff/invite",
    response_model=StaffInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_staff(
    dealership_id: int,
    payload: StaffInvitationRequest,
    current_user: User = Depends(require_roles("dealership_admin")),
    db: Session = Depends(get_db),
) -> StaffInvitation:
    if current_user.dealership_id != dealership_id:
        raise HTTPException(status_code=404, detail="Dealership not found")
    email = str(payload.email).lower()
    existing = user_repository.get_by_email(db, email)
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")

    invitation_token = secrets.token_urlsafe(48)
    temporary_password = secrets.token_urlsafe(16)
    invited_user = user_repository.create(
        db,
        name=payload.name,
        email=email,
        password=auth_service.hash_password(temporary_password),
        role=payload.role,
        dealership_id=dealership_id,
        must_change_password=True,
        commit=False,
    )
    invitation = StaffInvitation(
        dealership_id=dealership_id,
        invited_by_user_id=current_user.id,
        user_id=invited_user.id,
        email=email,
        role=payload.role,
        activation_token=invitation_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db.add(invitation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to create staff invitation") from exc
    db.refresh(invitation)
    dealership = db.get(Dealership, dealership_id)
    delivery_status = send_staff_invitation(
        recipient=invitation.email,
        dealership_name=dealership.name if dealership else "your dealership",
        temporary_password=temporary_password,
        activation_token=invitation.activation_token,
    )
    return StaffInvitationResponse(
        user_id=invited_user.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        delivery_status=delivery_status,
    )


@router.post("/auth/activate-invitation", response_model=UserResponse)
def activate_invitation(
    payload: ActivationRequest,
    db: Session = Depends(get_db),
) -> User:
    invitation = db.scalar(
        select(StaffInvitation).where(
            StaffInvitation.activation_token == payload.token,
            StaffInvitation.accepted_at.is_(None),
            StaffInvitation.revoked_at.is_(None),
        )
    )
    if invitation is None or _utc(invitation.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invitation is invalid or expired")
    user = db.get(User, invitation.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invited account is unavailable")
    user.password = auth_service.hash_password(payload.password)
    user.must_change_password = False
    invitation.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/dealerships/{dealership_id}/vehicles",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vehicle(
    dealership_id: int,
    payload: VehicleCreateRequest,
    current_user: User = Depends(
        require_roles("dealership_admin", "manager", "sales_rep")
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    if current_user.dealership_id != dealership_id:
        raise HTTPException(status_code=404, detail="Dealership not found")
    vehicle = Vehicle(dealership_id=dealership_id, **payload.model_dump())
    db.add(vehicle)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Stock number already exists") from exc
    db.refresh(vehicle)
    return vehicle


@router.get(
    "/dealerships/{dealership_id}/vehicles",
    response_model=list[VehicleResponse],
)
def list_vehicles(
    dealership_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Vehicle]:
    if current_user.dealership_id != dealership_id:
        raise HTTPException(status_code=404, detail="Dealership not found")
    return list(
        db.scalars(
            select(Vehicle)
            .where(Vehicle.dealership_id == dealership_id)
            .order_by(Vehicle.id)
        )
    )


@router.put(
    "/dealerships/{dealership_id}/test-drive-settings",
    response_model=TestDriveSettingsResponse,
)
def update_test_drive_settings(
    dealership_id: int,
    payload: TestDriveSettingsRequest,
    current_user: User = Depends(require_roles("dealership_admin")),
    db: Session = Depends(get_db),
) -> TestDriveSettings:
    if current_user.dealership_id != dealership_id:
        raise HTTPException(status_code=404, detail="Dealership not found")
    opening = _parse_time(payload.opening_time)
    closing = _parse_time(payload.closing_time)
    if opening >= closing:
        raise HTTPException(status_code=422, detail="Opening time must be before closing time")
    settings = db.scalar(
        select(TestDriveSettings).where(TestDriveSettings.dealership_id == dealership_id)
    )
    if settings is None:
        settings = TestDriveSettings(dealership_id=dealership_id)
        db.add(settings)
    settings.opening_time = payload.opening_time
    settings.closing_time = payload.closing_time
    settings.slot_duration_minutes = payload.slot_duration_minutes
    settings.capacity_per_slot = payload.capacity_per_slot
    settings.days_open = ",".join(str(day) for day in payload.days_open)
    db.commit()
    db.refresh(settings)
    return settings


@router.post(
    "/dealerships/{dealership_id}/test-drive-slots/generate",
    response_model=list[TestDriveSlotResponse],
)
def generate_test_drive_slots(
    dealership_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(require_roles("dealership_admin")),
    db: Session = Depends(get_db),
) -> list[TestDriveSlot]:
    if current_user.dealership_id != dealership_id:
        raise HTTPException(status_code=404, detail="Dealership not found")
    if end_date < start_date or (end_date - start_date).days > 90:
        raise HTTPException(status_code=422, detail="Date range must be 0 to 90 days")
    settings = db.scalar(
        select(TestDriveSettings).where(TestDriveSettings.dealership_id == dealership_id)
    )
    if settings is None:
        raise HTTPException(status_code=422, detail="Configure test-drive settings first")
    vehicles = list(
        db.scalars(
            select(Vehicle).where(
                Vehicle.dealership_id == dealership_id,
                Vehicle.is_available.is_(True),
                Vehicle.test_drive_enabled.is_(True),
            )
        )
    )
    opening = _parse_time(settings.opening_time)
    closing = _parse_time(settings.closing_time)
    open_days = {int(day) for day in settings.days_open.split(",") if day}
    created: list[TestDriveSlot] = []
    current_day = start_date
    while current_day <= end_date:
        if current_day.weekday() in open_days:
            slot_start = datetime.combine(current_day, opening)
            closing_at = datetime.combine(current_day, closing)
            while slot_start + timedelta(minutes=settings.slot_duration_minutes) <= closing_at:
                slot_end = slot_start + timedelta(minutes=settings.slot_duration_minutes)
                for vehicle in vehicles:
                    exists = db.scalar(
                        select(TestDriveSlot).where(
                            TestDriveSlot.dealership_id == dealership_id,
                            TestDriveSlot.vehicle_id == vehicle.id,
                            TestDriveSlot.starts_at == slot_start,
                        )
                    )
                    if exists is None:
                        slot = TestDriveSlot(
                            dealership_id=dealership_id,
                            vehicle_id=vehicle.id,
                            starts_at=slot_start,
                            ends_at=slot_end,
                            capacity=settings.capacity_per_slot,
                        )
                        db.add(slot)
                        created.append(slot)
                slot_start = slot_end
        current_day += timedelta(days=1)
    db.commit()
    for slot in created:
        db.refresh(slot)
    return created


def _parse_time(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour=hour, minute=minute)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
