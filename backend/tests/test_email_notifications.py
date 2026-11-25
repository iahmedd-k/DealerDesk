from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import (
    dealership_service,
    email_service,
    lead_service,
    otp_service,
    test_drive_service,
)

pytestmark = pytest.mark.no_db


def test_all_email_templates_render_html_and_text_with_escaping(monkeypatch) -> None:
    captured: list[dict] = []

    def fake_send(payload: dict) -> str:
        captured.append(payload)
        return "email_sent"

    monkeypatch.setattr(email_service, "_send_resend_email", fake_send)

    email_service.send_staff_invitation(
        recipient="staff@example.com",
        dealership_name="Apex <Motors>",
        temporary_password="TempPass<123>",
        activation_token="tok_123",
    )
    email_service.send_password_reset(recipient="user@example.com", reset_token="rst_456")
    email_service.send_email_verification(recipient="user@example.com", verification_token="ver_789")
    email_service.send_otp_email(recipient="user@example.com", code="654321")
    email_service.send_password_changed_alert(recipient="user@example.com", user_name="Ahmed")
    email_service.send_dealership_welcome(
        recipient="admin@example.com",
        admin_name="Ahmed",
        dealership_name="Apex Motors",
        dealership_email="sales@apex.com",
        timezone_name="America/New_York",
    )
    email_service.send_test_drive_confirmation(
        recipient="cust@example.com",
        customer_name="Jane",
        dealership_name="Apex Motors",
        dealership_address="123 Main St",
        dealership_phone="+1-555-0100",
        vehicle_label="2025 Toyota Camry",
        stock_number="CAM-001",
        starts_at_local="Nov 26, 2026 at 10:00 AM",
        ends_at_local="10:30 AM",
        timezone_name="America/New_York",
        booking_id=42,
    )
    email_service.send_test_drive_rescheduled(
        recipient="cust@example.com",
        customer_name="Jane",
        dealership_name="Apex Motors",
        dealership_address="123 Main St",
        vehicle_label="2025 Toyota Camry",
        starts_at_local="Nov 27, 2026 at 02:00 PM",
        ends_at_local="02:30 PM",
        timezone_name="America/New_York",
        booking_id=42,
    )
    email_service.send_test_drive_cancelled(
        recipient="cust@example.com",
        customer_name="Jane",
        dealership_name="Apex Motors",
        vehicle_label="2025 Toyota Camry",
        starts_at_local="Nov 27, 2026 at 02:00 PM",
        timezone_name="America/New_York",
        booking_id=42,
    )
    email_service.send_lead_acknowledgment(
        recipient="cust@example.com",
        customer_name="Jane",
        dealership_name="Apex Motors",
        dealership_phone="+1-555-0100",
        vehicle_label="2025 Toyota Camry",
    )
    email_service.send_new_lead_alert(
        recipient="sales@apex.com",
        dealership_name="Apex Motors",
        lead_name="Jane",
        lead_email="cust@example.com",
        lead_phone="+1-555-0199",
        source="whatsapp",
        vehicle_label="2025 Toyota Camry",
        message="Interested in <script>alert(1)</script> financing",
    )
    email_service.send_lead_assigned_notification(
        recipient="rep@apex.com",
        staff_name="Ali",
        dealership_name="Apex Motors",
        lead_name="Jane",
        lead_email="cust@example.com",
        lead_phone="+1-555-0199",
        vehicle_label="2025 Toyota Camry",
        message="Call after 5pm",
        lead_id=99,
    )

    assert len(captured) == 12
    for payload in captured:
        assert payload["from"]
        assert payload["to"]
        assert payload["subject"]
        assert payload["text"]
        assert "<!DOCTYPE html>" in payload["html"]
        assert "Dealer" in payload["html"]
        assert "<script>" not in payload["html"]

    # Check HTML escaping on the first and eleventh payloads
    assert "Apex &lt;Motors&gt;" in captured[0]["html"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in captured[10]["html"]


def test_synthetic_local_email_is_skipped() -> None:
    status = email_service._send_resend_email(
        {
            "to": ["phone_14155550100@customer.dealerdesk.local"],
            "subject": "Test",
            "text": "Hello",
        }
    )
    assert status == "email_skipped_synthetic"


def test_resend_pending_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    status = email_service._send_resend_email(
        {
            "to": ["real@example.com"],
            "subject": "Test",
            "text": "Hello",
        }
    )
    assert status == "email_provider_pending"


def test_test_drive_booking_reschedule_cancel_trigger_emails(monkeypatch) -> None:
    sent_events: list[tuple[str, str]] = []

    monkeypatch.setattr(
        email_service,
        "send_test_drive_confirmation",
        lambda **kw: sent_events.append(("confirmed", kw["recipient"])) or "email_sent",
    )
    monkeypatch.setattr(
        email_service,
        "send_test_drive_rescheduled",
        lambda **kw: sent_events.append(("rescheduled", kw["recipient"])) or "email_sent",
    )
    monkeypatch.setattr(
        email_service,
        "send_test_drive_cancelled",
        lambda **kw: sent_events.append(("cancelled", kw["recipient"])) or "email_sent",
    )

    dealership = SimpleNamespace(
        id=1,
        name="Apex Motors",
        address="100 Auto Way",
        phone="555-1234",
        timezone="UTC",
    )
    vehicle = SimpleNamespace(
        id=10,
        brand_id=2,
        make="Toyota",
        model="Camry",
        model_year=2025,
        stock_number="STK-1",
        is_available=True,
        test_drive_enabled=True,
    )
    brand = SimpleNamespace(id=2, is_active=True, is_deleted=False)
    future_start = datetime.now(timezone.utc) + timedelta(days=2)
    slot1 = SimpleNamespace(
        id=100,
        dealership_id=1,
        vehicle_id=10,
        starts_at=future_start,
        ends_at=future_start + timedelta(minutes=30),
        capacity=2,
        booked_count=0,
        is_active=True,
    )
    slot2 = SimpleNamespace(
        id=101,
        dealership_id=1,
        vehicle_id=10,
        starts_at=future_start + timedelta(hours=2),
        ends_at=future_start + timedelta(hours=2, minutes=30),
        capacity=2,
        booked_count=0,
        is_active=True,
    )
    customer = SimpleNamespace(id=5, name="Jane Doe", email="jane@example.com", role="customer")
    booking = SimpleNamespace(
        id=55,
        slot_id=100,
        dealership_id=1,
        vehicle_id=10,
        customer_id=5,
        status="booked",
        cancelled_at=None,
    )

    monkeypatch.setattr(
        test_drive_service.dealership_service,
        "get_active_dealership",
        lambda db, did: dealership,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "get_slot",
        lambda db, did, sid, lock=False: slot1 if sid == 100 else slot2,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "get_slot_by_id",
        lambda db, sid, lock=False: slot1 if sid == 100 else slot2,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "get_vehicle",
        lambda db, vid: vehicle,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "get_brand",
        lambda db, bid: brand,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "lock_customer",
        lambda db, cid: None,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "has_booking",
        lambda db, sid, cid: False,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "has_overlapping_booking",
        lambda db, cid, s, e, exclude_slot_id=None: False,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "create_booking",
        lambda db, b, s: booking,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "get_booking",
        lambda db, did, bid, lock=False: booking,
    )
    monkeypatch.setattr(
        test_drive_service.test_drive_repository,
        "save",
        lambda db, *args: None,
    )
    monkeypatch.setattr(
        test_drive_service.user_repository,
        "get_by_id",
        lambda db, uid: customer,
    )

    from app.services import slot_hold_service

    monkeypatch.setattr(slot_hold_service, "get_active_holds_count_for_slot", lambda db, sid: 0)

    db = MagicMock()
    test_drive_service.book_slot(db, 1, 100, customer)
    test_drive_service.reschedule_booking(
        db,
        1,
        55,
        SimpleNamespace(confirmed=True, verification_email=None, new_slot_id=101),
        customer,
    )
    test_drive_service.cancel_booking(db, 1, 55, customer)

    assert sent_events == [
        ("confirmed", "jane@example.com"),
        ("rescheduled", "jane@example.com"),
        ("cancelled", "jane@example.com"),
    ]


def test_lead_notifications_and_assignment_emails(monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    monkeypatch.setattr(
        email_service,
        "send_lead_acknowledgment",
        lambda **kw: events.append(("ack", kw["recipient"])) or "email_sent",
    )
    monkeypatch.setattr(
        email_service,
        "send_new_lead_alert",
        lambda **kw: events.append(("alert", kw["recipient"])) or "email_sent",
    )
    monkeypatch.setattr(
        email_service,
        "send_lead_assigned_notification",
        lambda **kw: events.append(("assigned", kw["recipient"])) or "email_sent",
    )

    dealership = SimpleNamespace(id=1, name="Apex Motors", email="sales@apex.com", phone="555-0000")
    staff_user = SimpleNamespace(id=7, name="Rep Ali", email="ali@apex.com")
    lead = SimpleNamespace(
        id=88,
        dealership_id=1,
        name="Bob Buyer",
        email="bob@example.com",
        phone="555-9999",
        source="website",
        requested_vehicle_id=None,
        message="Looking for SUV",
        assigned_to_user_id=None,
        test_drive_booking_id=None,
        status="new",
        next_follow_up_at=None,
    )

    monkeypatch.setattr(lead_service.dealership_repository, "get_by_id", lambda db, did: dealership)
    monkeypatch.setattr(lead_service.lead_repository, "get_vehicle", lambda db, did, vid: None)
    monkeypatch.setattr(lead_service.lead_repository, "get_lead", lambda db, did, lid: lead)
    monkeypatch.setattr(lead_service.lead_repository, "get_staff_user", lambda db, did, uid: staff_user)
    monkeypatch.setattr(lead_service.lead_repository, "save", lambda db, obj: obj)

    db = MagicMock()
    lead_service.notify_new_lead(db, 1, lead)

    admin = SimpleNamespace(id=1, role="dealership_admin", dealership_id=1)
    payload = MagicMock()
    payload.model_fields_set = {"assigned_to_user_id"}
    payload.model_dump.return_value = {"assigned_to_user_id": 7}
    lead_service.update_lead(db, 1, 88, admin, payload)

    assert events == [
        ("ack", "bob@example.com"),
        ("alert", "sales@apex.com"),
        ("assigned", "ali@apex.com"),
    ]


def test_otp_and_dealership_welcome_dispatch(monkeypatch) -> None:
    dispatched: list[str] = []

    monkeypatch.setattr(
        email_service,
        "send_otp_email",
        lambda **kw: dispatched.append(f"otp:{kw['recipient']}:{kw['code']}") or "email_sent",
    )
    monkeypatch.setattr(
        email_service,
        "send_dealership_welcome",
        lambda **kw: dispatched.append(f"welcome:{kw['recipient']}:{kw['dealership_name']}") or "email_sent",
    )

    otp_service._dispatch_otp_message(1, "email", "buyer@example.com", "123456", "test_drive_booking")

    monkeypatch.setattr(dealership_service.user_repository, "get_by_email", lambda db, e: None)
    monkeypatch.setattr(
        dealership_service.dealership_repository,
        "create_registration",
        lambda db, **kw: SimpleNamespace(id=10, email=kw["admin_email"]),
    )

    payload = SimpleNamespace(
        admin_email="owner@newdealer.com",
        dealership_email="hello@newdealer.com",
        dealership_name="New Dealer",
        dealership_phone="555-2222",
        dealership_address="1 Road",
        timezone="UTC",
        brands=["Toyota"],
        admin_name="Owner",
        admin_password="StrongPassword123!",
    )
    dealership_service.register_dealership(MagicMock(), payload)

    assert dispatched == [
        "otp:buyer@example.com:123456",
        "welcome:owner@newdealer.com:New Dealer",
    ]
