from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import email_service, reminder_service

pytestmark = pytest.mark.no_db


def test_process_due_reminders_dispatches_24h_and_2h_idempotently(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    dealership = SimpleNamespace(
        id=1,
        name="Apex Motors",
        address="100 Auto Way",
        phone="555-1234",
        timezone="UTC",
        is_active=True,
    )
    vehicle = SimpleNamespace(
        id=10,
        make="Toyota",
        model="Camry",
        model_year=2025,
        stock_number="STK-10",
    )
    customer = SimpleNamespace(id=5, name="Jane", email="jane@example.com")

    booking_24h = SimpleNamespace(id=101, status="booked")
    slot_24h = SimpleNamespace(
        starts_at=now + timedelta(hours=12),
        ends_at=now + timedelta(hours=12, minutes=30),
    )
    booking_2h = SimpleNamespace(id=102, status="booked")
    slot_2h = SimpleNamespace(
        starts_at=now + timedelta(minutes=90),
        ends_at=now + timedelta(minutes=120),
    )

    sent_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        email_service,
        "send_test_drive_reminder",
        lambda **kw: sent_calls.append((kw["booking_id"], kw["hours_before"])) or "email_sent",
    )

    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (booking_24h, slot_24h, dealership, vehicle, customer),
        (booking_2h, slot_2h, dealership, vehicle, customer),
    ]
    # First booking not yet delivered, second booking already delivered
    db.scalar.side_effect = [None, SimpleNamespace(id=999)]

    report = reminder_service.process_due_booking_reminders(db, dry_run=False)

    assert report["evaluated"] == 2
    assert report["sent_24h"] == 1
    assert report["sent_2h"] == 0
    assert report["skipped_already_delivered"] == 1
    assert report["failed"] == 0
    assert sent_calls == [(101, 24)]
    db.add.assert_called_once()
    ledger_row = db.add.call_args[0][0]
    assert ledger_row.booking_id == 101
    assert ledger_row.notification_type == reminder_service.REMINDER_24H
    assert ledger_row.status == "sent"


def test_process_due_reminders_dry_run_does_not_send_or_commit(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    dealership = SimpleNamespace(
        id=1,
        name="Apex Motors",
        address="100 Auto Way",
        phone="555-1234",
        timezone="UTC",
        is_active=True,
    )
    vehicle = SimpleNamespace(
        id=10,
        make="Toyota",
        model="Camry",
        model_year=2025,
        stock_number="STK-10",
    )
    customer = SimpleNamespace(id=5, name="Jane", email="jane@example.com")
    booking_2h = SimpleNamespace(id=102, status="booked")
    slot_2h = SimpleNamespace(
        starts_at=now + timedelta(minutes=45),
        ends_at=now + timedelta(minutes=75),
    )

    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (booking_2h, slot_2h, dealership, vehicle, customer),
    ]
    db.scalar.return_value = None

    called = False

    def fail_if_called(**kw):
        nonlocal called
        called = True
        return "email_sent"

    monkeypatch.setattr(email_service, "send_test_drive_reminder", fail_if_called)

    report = reminder_service.process_due_booking_reminders(db, dry_run=True)

    assert report["dry_run"] is True
    assert report["sent_2h"] == 1
    assert called is False
    db.add.assert_not_called()
