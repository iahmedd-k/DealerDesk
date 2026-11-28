from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.errors import ConflictError
from app.services import email_service, lead_service, test_drive_service, vehicle_service

pytestmark = pytest.mark.no_db


def test_booked_lead_can_transition_to_won_and_marks_vehicle_sold(monkeypatch) -> None:
    lead = SimpleNamespace(
        id=10,
        dealership_id=1,
        name="Alice Buyer",
        email="alice@example.com",
        phone="555-0101",
        requested_vehicle_id=None,
        test_drive_booking_id=77,
        assigned_to_user_id=None,
        status="test_drive_scheduled",
        lost_reason=None,
        next_follow_up_at=None,
        deal_value=None,
        updated_at=None,
    )
    booking = SimpleNamespace(
        id=77,
        dealership_id=1,
        vehicle_id=50,
        customer_id=9,
        status="booked",
    )
    vehicle = SimpleNamespace(
        id=50,
        dealership_id=1,
        brand_id=3,
        make="Honda",
        model="Civic",
        model_year=2025,
        stock_number="HON-050",
        status="available",
        is_available=True,
        test_drive_enabled=True,
    )
    staff = SimpleNamespace(id=2, role="dealership_admin", dealership_id=1)

    monkeypatch.setattr(lead_service.lead_repository, "get_lead", lambda db, did, lid, **_kw: lead)
    monkeypatch.setattr(lead_service.lead_repository, "get_booking", lambda db, did, bid: booking)
    monkeypatch.setattr(lead_service.lead_repository, "get_vehicle", lambda db, did, vid, **_kw: vehicle)
    monkeypatch.setattr(lead_service.lead_repository, "save", lambda db, obj: obj)

    transitioned: list[tuple[int, str, str | None, str]] = []

    def fake_transition(db, did, vid, user, payload):
        transitioned.append((vid, payload.status, payload.notes, lead.status))
        vehicle.status = payload.status
        vehicle.is_available = False
        vehicle.test_drive_enabled = False
        return vehicle

    monkeypatch.setattr(lead_service.vehicle_service, "transition_vehicle_status", fake_transition)
    outbox_events = []
    monkeypatch.setattr(
        lead_service.outbox_service,
        "enqueue_event",
        lambda _db, **kwargs: outbox_events.append(kwargs),
    )

    db = MagicMock()

    # Invalid backward move on booked lead should still raise ConflictError
    bad_payload = MagicMock()
    bad_payload.model_fields_set = {"status"}
    bad_payload.model_dump.return_value = {"status": "new"}
    with pytest.raises(ConflictError):
        lead_service.update_lead(db, 1, 10, staff, bad_payload)

    # Valid transition to 'won' should complete booking and mark vehicle 'sold'
    won_payload = MagicMock()
    won_payload.model_fields_set = {"status"}
    won_payload.model_dump.return_value = {"status": "won"}
    updated_lead = lead_service.update_lead(db, 1, 10, staff, won_payload)

    assert updated_lead.status == "won"
    assert booking.status == "completed"
    assert transitioned == [(50, "sold", "Sold via Lead #10 (Alice Buyer)", "won")]
    assert outbox_events == [
        {
            "dealership_id": 1,
            "event_type": "lead.won",
            "aggregate_type": "customer_lead",
            "aggregate_id": 10,
            "payload": {"lead_id": 10, "vehicle_id": 50, "deal_value": 0.0},
            "commit": False,
        }
    ]

    # Second lead trying to mark the same already-sold vehicle 'won' must be rejected
    second_lead = SimpleNamespace(
        id=11,
        dealership_id=1,
        name="Bob Second",
        email="bob@example.com",
        phone="555-0202",
        requested_vehicle_id=50,
        test_drive_booking_id=None,
        assigned_to_user_id=None,
        status="qualified",
        lost_reason=None,
        next_follow_up_at=None,
        updated_at=None,
    )
    monkeypatch.setattr(lead_service.lead_repository, "get_lead", lambda db, did, lid, **_kw: second_lead)
    with pytest.raises(ConflictError, match="already been sold"):
        lead_service.update_lead(db, 1, 11, staff, won_payload)


def test_marking_a_linked_lead_lost_cancels_its_active_booking(monkeypatch) -> None:
    from app.schemas.workspace import CustomerLeadUpdateRequest

    lead = SimpleNamespace(
        id=10,
        dealership_id=1,
        name="Alice Buyer",
        email="alice@example.com",
        requested_vehicle_id=None,
        test_drive_booking_id=77,
        assigned_to_user_id=None,
        status="test_drive_scheduled",
        lost_reason=None,
        next_follow_up_at=None,
        updated_at=None,
        deal_value=None,
    )
    booking = SimpleNamespace(id=77, status="booked", vehicle_id=50)
    staff = SimpleNamespace(id=2, role="manager", dealership_id=1)
    events = []
    cancellations = []

    monkeypatch.setattr(
        lead_service.lead_repository,
        "get_lead",
        lambda *_args, **_kwargs: lead,
    )
    monkeypatch.setattr(
        lead_service.lead_repository,
        "get_booking",
        lambda *_args, **_kwargs: booking,
    )
    monkeypatch.setattr(lead_service.lead_repository, "save", lambda _db, obj: obj)
    monkeypatch.setattr(lead_service, "_record_activity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        lead_service.outbox_service,
        "enqueue_event",
        lambda _db, **kwargs: events.append(kwargs),
    )

    def cancel_booking(_db, _dealership_id, booking_id, _user, payload):
        cancellations.append((booking_id, payload.reason, lead.status))
        booking.status = "cancelled"

    monkeypatch.setattr(lead_service.test_drive_service, "cancel_booking", cancel_booking)

    updated = lead_service.update_lead(
        MagicMock(),
        1,
        10,
        staff,
        CustomerLeadUpdateRequest(status="lost"),
    )

    assert updated.status == "lost"
    assert booking.status == "cancelled"
    assert cancellations == [(77, "Lead marked lost", "lost")]
    assert events[0]["event_type"] == "lead.lost"
    assert events[0]["commit"] is False


def test_vehicle_sold_cleanup_deactivates_slots_releases_holds_and_cancels_bookings(
    monkeypatch,
) -> None:
    future = datetime.now(timezone.utc) + timedelta(days=1)
    slot = SimpleNamespace(
        id=201,
        dealership_id=1,
        vehicle_id=50,
        starts_at=future,
        ends_at=future + timedelta(minutes=30),
        capacity=2,
        booked_count=1,
        is_active=True,
    )
    hold = SimpleNamespace(id=301, dealership_id=1, slot_id=201, status="active")
    booking = SimpleNamespace(
        id=401,
        dealership_id=1,
        vehicle_id=50,
        slot_id=201,
        customer_id=88,
        status="booked",
        cancelled_at=None,
    )
    customer = SimpleNamespace(id=88, name="Carl", email="carl@example.com")
    dealership = SimpleNamespace(id=1, name="Apex Motors", timezone="UTC")
    vehicle = SimpleNamespace(
        id=50,
        dealership_id=1,
        make="Honda",
        model="Civic",
        model_year=2025,
        stock_number="HON-050",
    )

    db = MagicMock()
    db.scalars.side_effect = [
        [slot],     # future_slots
        [hold],     # active_holds
        [booking],  # booked_future
    ]
    monkeypatch.setattr(vehicle_service.user_repository, "get_by_id", lambda db, cid: customer)
    monkeypatch.setattr(vehicle_service.dealership_repository, "get_by_id", lambda db, did: dealership)

    cancelled_emails: list[tuple[str, int]] = []
    monkeypatch.setattr(
        email_service,
        "send_test_drive_cancelled",
        lambda **kw: cancelled_emails.append((kw["recipient"], kw["booking_id"])) or "email_sent",
    )

    vehicle_service._cleanup_bookings_and_slots_on_unavailable(db, 1, vehicle)

    assert slot.is_active is False
    assert slot.booked_count == 0
    assert hold.status == "released"
    assert booking.status == "cancelled"
    assert booking.cancelled_at is not None
    assert cancelled_emails == [("carl@example.com", 401)]


def test_booking_auto_links_open_lead_or_creates_new_lead() -> None:
    vehicle = SimpleNamespace(
        id=50,
        make="Honda",
        model="Civic",
        model_year=2025,
        stock_number="HON-050",
    )
    customer = SimpleNamespace(id=9, name="Alice Buyer", email="alice@example.com")
    booking = SimpleNamespace(id=77)

    # Case 1: Existing open lead is auto-linked
    existing_lead = SimpleNamespace(
        id=10,
        dealership_id=1,
        customer_id=None,
        requested_vehicle_id=None,
        test_drive_booking_id=None,
        status="qualified",
        next_follow_up_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    db1 = MagicMock()
    db1.scalar.return_value = existing_lead
    test_drive_service._sync_lead_for_booking(db1, 1, booking, vehicle, customer)

    assert existing_lead.test_drive_booking_id == 77
    assert existing_lead.status == "test_drive_scheduled"
    assert existing_lead.requested_vehicle_id == 50
    assert existing_lead.next_follow_up_at is None
    db1.commit.assert_called_once()

    # Case 2: No existing lead -> creates a new CustomerLead in test_drive_scheduled
    db2 = MagicMock()
    db2.scalar.return_value = None
    test_drive_service._sync_lead_for_booking(db2, 1, booking, vehicle, customer)

    db2.add.assert_called_once()
    created_lead = db2.add.call_args[0][0]
    assert created_lead.dealership_id == 1
    assert created_lead.customer_id == 9
    assert created_lead.requested_vehicle_id == 50
    assert created_lead.test_drive_booking_id == 77
    assert created_lead.status == "test_drive_scheduled"
    assert created_lead.source == "test_drive"
    db2.commit.assert_called_once()
