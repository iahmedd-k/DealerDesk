from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.models.workspace import (
    TestDriveBooking,
    TestDriveSettings,
    TestDriveSlot,
)
from app.schemas.workspace import (
    TestDriveBookingResponse,
    TestDriveSettingsRequest,
    TestDriveSettingsResponse,
    TestDriveSlotResponse,
    TestDriveSlotUpdateRequest,
)
from app.services import test_drive_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}",
    tags=["Test Drives"],
)


@router.get("/test-drive-settings", response_model=TestDriveSettingsResponse)
def get_test_drive_settings(
    dealership_id: int,
    db: Session = Depends(get_db),
) -> TestDriveSettings:
    return test_drive_service.get_settings(db, dealership_id)


@router.put("/test-drive-settings", response_model=TestDriveSettingsResponse)
def update_test_drive_settings(
    dealership_id: int,
    payload: TestDriveSettingsRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> TestDriveSettings:
    return test_drive_service.update_settings(
        db,
        dealership_id,
        current_user,
        payload,
    )


@router.post(
    "/test-drive-slots/generate",
    response_model=list[TestDriveSlotResponse],
)
def generate_test_drive_slots(
    dealership_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> list[TestDriveSlot]:
    return test_drive_service.generate_slots(
        db,
        dealership_id,
        current_user,
        start_date,
        end_date,
    )


@router.delete("/test-drive-settings", status_code=204)
def delete_test_drive_settings(
    dealership_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    test_drive_service.delete_settings(db, dealership_id, current_user)


@router.get("/test-drive-slots", response_model=list[TestDriveSlotResponse])
def list_test_drive_slots(
    dealership_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> list[TestDriveSlot]:
    return test_drive_service.list_slots(
        db,
        dealership_id,
        include_inactive=include_inactive,
    )


@router.get("/test-drive-slots/{slot_id}", response_model=TestDriveSlotResponse)
def get_test_drive_slot(
    dealership_id: int,
    slot_id: int,
    db: Session = Depends(get_db),
) -> TestDriveSlot:
    return test_drive_service.get_slot(db, dealership_id, slot_id)


@router.patch("/test-drive-slots/{slot_id}", response_model=TestDriveSlotResponse)
def update_test_drive_slot(
    dealership_id: int,
    slot_id: int,
    payload: TestDriveSlotUpdateRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> TestDriveSlot:
    return test_drive_service.update_slot(
        db,
        dealership_id,
        slot_id,
        current_user,
        payload,
    )


@router.delete("/test-drive-slots/{slot_id}", status_code=204)
def delete_test_drive_slot(
    dealership_id: int,
    slot_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    test_drive_service.delete_slot(db, dealership_id, slot_id, current_user)


@router.get(
    "/test-drive-slots/{slot_id}/bookings",
    response_model=list[TestDriveBookingResponse],
)
def list_bookings(
    dealership_id: int,
    slot_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TestDriveBooking]:
    return test_drive_service.list_bookings_for_slot(
        db,
        dealership_id,
        slot_id,
        current_user,
    )


@router.get("/test-drive-bookings", response_model=list[TestDriveBookingResponse])
def list_customer_bookings(
    dealership_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TestDriveBooking]:
    return test_drive_service.list_customer_bookings(
        db,
        dealership_id,
        current_user,
    )


@router.post(
    "/test-drive-slots/{slot_id}/bookings",
    response_model=TestDriveBookingResponse,
    status_code=201,
)
def book_test_drive(
    dealership_id: int,
    slot_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TestDriveBooking:
    return test_drive_service.book_slot(db, dealership_id, slot_id, current_user)


@router.delete("/test-drive-bookings/{booking_id}", status_code=204)
def cancel_test_drive(
    dealership_id: int,
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    test_drive_service.cancel_booking(
        db,
        dealership_id,
        booking_id,
        current_user,
    )
