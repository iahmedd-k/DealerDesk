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
