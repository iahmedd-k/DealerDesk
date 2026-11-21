from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.services.test_drive_service import _slots_for_day
from app.schemas.workspace import DealershipRegistrationRequest


def test_slot_generation_uses_local_timezone_and_skips_nonexistent_dst_times() -> None:
    slots = _slots_for_day(
        date(2027, 3, 14),
        time(1, 0),
        time(4, 0),
        30,
        ZoneInfo("America/New_York"),
    )

    local_starts = [
        starts_at.astimezone(ZoneInfo("America/New_York")) for starts_at, _ in slots
    ]
    assert [start.hour for start in local_starts] == [1, 3, 3]
    assert all(
        ends_at - starts_at == timedelta(minutes=30) for starts_at, ends_at in slots
    )


def test_dealership_registration_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        DealershipRegistrationRequest.model_validate(
            {
                "dealership_name": "Invalid Timezone",
                "dealership_email": "invalid-timezone@example.com",
                "admin_name": "Admin",
                "admin_email": "timezone-admin@example.com",
                "admin_password": "Password!123",
                "timezone": "Not/A_Timezone",
                "brands": ["Toyota"],
            }
        )


def test_slot_response_computed_fields() -> None:
    from datetime import datetime, timezone
    from app.schemas.workspace import TestDriveSlotResponse, TestDriveBookingRequest

    now = datetime.now(timezone.utc)
    slot = TestDriveSlotResponse(
        id=1,
        vehicle_id=10,
        starts_at=now,
        ends_at=now + timedelta(minutes=30),
        capacity=3,
        booked_count=1,
        is_active=True,
    )
    assert slot.remaining_capacity == 2
    assert slot.is_available is True

    full_slot = TestDriveSlotResponse(
        id=2,
        vehicle_id=10,
        starts_at=now,
        ends_at=now + timedelta(minutes=30),
        capacity=2,
        booked_count=2,
        is_active=True,
    )
    assert full_slot.remaining_capacity == 0
    assert full_slot.is_available is False

    inactive_slot = TestDriveSlotResponse(
        id=3,
        vehicle_id=10,
        starts_at=now,
        ends_at=now + timedelta(minutes=30),
        capacity=2,
        booked_count=0,
        is_active=False,
    )
    assert inactive_slot.remaining_capacity == 2
    assert inactive_slot.is_available is False

    # FR-017 Booking explicit confirmation schema
    default_req = TestDriveBookingRequest()
    assert default_req.confirmed is True

    confirmed_req = TestDriveBookingRequest(confirmed=True)
    assert confirmed_req.confirmed is True

    unconfirmed_req = TestDriveBookingRequest(confirmed=False)
    assert unconfirmed_req.confirmed is False
