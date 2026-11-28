from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.v1.endpoints.notifications import list_in_app_notifications

pytestmark = pytest.mark.no_db


def test_notification_center_combines_overdue_handoffs_and_upcoming_drives() -> None:
    now = datetime.now(timezone.utc)
    lead = SimpleNamespace(
        id=11,
        name="Sam Rivera",
        next_follow_up_at=now - timedelta(hours=1),
    )
    conversation = SimpleNamespace(
        id=21,
        channel="email",
        channel_user_id="sam@example.com",
        channel_metadata={"assigned_to_user_id": 1},
        updated_at=now - timedelta(minutes=10),
    )
    booking = SimpleNamespace(id=31)
    slot = SimpleNamespace(starts_at=now + timedelta(hours=2))
    manager = SimpleNamespace(id=1, role="manager", dealership_id=7)
    db = MagicMock()
    db.scalars.side_effect = [[lead], [conversation]]
    db.execute.return_value = [(booking, slot)]

    notifications = list_in_app_notifications(7, manager, db)

    assert {item.id for item in notifications} == {
        "lead-overdue-11",
        "handoff-21",
        "booking-upcoming-31",
    }
    assert [item.created_at for item in notifications] == sorted(
        [item.created_at for item in notifications], reverse=True
    )
    assert next(item for item in notifications if item.id == "handoff-21").href == "/inbox"


def test_notification_center_includes_handoffs_assigned_to_sales_rep() -> None:
    now = datetime.now(timezone.utc)
    assigned = SimpleNamespace(
        id=21,
        channel="website",
        channel_user_id="visitor-1",
        channel_metadata={"assigned_to_user_id": "4"},
        updated_at=now,
    )
    sales_rep = SimpleNamespace(id=4, role="sales_rep", dealership_id=7)
    db = MagicMock()
    db.scalars.side_effect = [[], [assigned]]
    db.execute.return_value = []

    notifications = list_in_app_notifications(7, sales_rep, db)

    assert [item.id for item in notifications] == ["handoff-21"]
