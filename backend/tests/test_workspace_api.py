from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.workspace import Vehicle
from app.schemas.workspace import VehicleCreateRequest
from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_PASSWORD,
    DEALERDESK_ADMIN_DEMO_EMAIL,
    DEALERDESK_ADMIN_DEMO_PASSWORD,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_PASSWORD,
)


def test_vehicle_price_uses_decimal_with_two_fractional_digits() -> None:
    vehicle = VehicleCreateRequest(
        brand_id=1,
        model="Vehicle",
        model_year=2026,
        price="10000.25",
        stock_number="TEST-001",
    )
    assert vehicle.price == Decimal("10000.25")

    with pytest.raises(ValidationError):
        VehicleCreateRequest(
            brand_id=1,
            model="Vehicle",
            model_year=2026,
            price="10000.257",
            stock_number="TEST-002",
        )


def test_customer_cannot_create_dealership_vehicle(client, seeded_users) -> None:
    customer_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": CUSTOMER_DEMO_EMAIL,
            "password": CUSTOMER_DEMO_PASSWORD,
        },
    )
    dealership_id = seeded_users[1].dealership_id

    response = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers={"Authorization": f"Bearer {customer_login.json()['access_token']}"},
        json={
            "brand_id": 1,
            "model": "Vehicle",
            "model_year": 2026,
            "price": 10000,
            "stock_number": "DEMO-001",
        },
    )

    assert response.status_code == 403


def test_dealership_admin_can_manage_vehicle_and_settings(
    client,
    db,
    seeded_users,
) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": DEALERSHIP_DEMO_EMAIL, "password": DEALERSHIP_DEMO_PASSWORD},
    )
    token = login.json()["access_token"]
    dealership_id = seeded_users[1].dealership_id
    headers = {"Authorization": f"Bearer {token}"}
    brands = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
    )
    assert brands.status_code == 200
    brand_id = brands.json()[0]["id"]

    vehicle = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=headers,
        json={
            "brand_id": brand_id,
            "model": "Vehicle",
            "model_year": 2026,
            "price": 10000.25,
            "stock_number": "DEMO-001",
            "test_drive_enabled": True,
        },
    )
    settings = client.put(
        f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
        headers=headers,
        json={"opening_time": "09:00", "closing_time": "10:00"},
    )

    assert vehicle.status_code == 201
    assert vehicle.json()["price"] == 10000.25
    stored_vehicle = db.query(Vehicle).filter_by(stock_number="DEMO-001").one()
    assert stored_vehicle.price == Decimal("10000.25")
    assert settings.status_code == 200


def test_dealerdesk_admin_full_access_and_customer_isolation(client, seeded_users) -> None:
    # 1. DealerDesk admin login
    dealerdesk_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": DEALERDESK_ADMIN_DEMO_EMAIL,
            "password": DEALERDESK_ADMIN_DEMO_PASSWORD,
        },
    )
    assert dealerdesk_login.status_code == 200
    dealerdesk_token = dealerdesk_login.json()["access_token"]
    dealerdesk_headers = {"Authorization": f"Bearer {dealerdesk_token}"}

    # 2. Customer login
    customer_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": CUSTOMER_DEMO_EMAIL,
            "password": CUSTOMER_DEMO_PASSWORD,
        },
    )
    assert customer_login.status_code == 200
    customer_token = customer_login.json()["access_token"]
    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    dealership_id = seeded_users[1].dealership_id

    # DealerDesk admin can list all workspaces
    dealerships_res = client.get("/api/v1/dealerships", headers=dealerdesk_headers)
    assert dealerships_res.status_code == 200
    assert len(dealerships_res.json()) >= 1

    # Customer and unauthenticated cannot list workspaces
    assert client.get("/api/v1/dealerships").status_code == 401
    assert client.get("/api/v1/dealerships", headers=customer_headers).status_code == 403

    # DealerDesk admin can access any workspace details
    assert client.get(f"/api/v1/dealerships/{dealership_id}", headers=dealerdesk_headers).status_code == 200

    # Customer cannot access workspace details
    assert client.get(f"/api/v1/dealerships/{dealership_id}", headers=customer_headers).status_code == 404

    # DealerDesk admin can access test-drive-settings across workspaces
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
            headers=dealerdesk_headers,
        ).status_code
        == 200
    )

    # Customer cannot access test-drive-settings
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
            headers=customer_headers,
        ).status_code
        == 403
    )


def test_fr016_fr017_testdrive_availability_and_booking(client, seeded_users) -> None:
    dealership_id = seeded_users[1].dealership_id

    # Dealership admin login
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": DEALERSHIP_DEMO_EMAIL, "password": DEALERSHIP_DEMO_PASSWORD},
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Customer login
    customer_login = client.post(
        "/api/v1/auth/login",
        json={"email": CUSTOMER_DEMO_EMAIL, "password": CUSTOMER_DEMO_PASSWORD},
    )
    assert customer_login.status_code == 200
    customer_headers = {"Authorization": f"Bearer {customer_login.json()['access_token']}"}

    # 1. Setup dealership test drive settings: capacity 1 for strict capacity testing
    settings_res = client.put(
        f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
        headers=admin_headers,
        json={"capacity_per_slot": 1, "slot_duration_minutes": 30},
    )
    assert settings_res.status_code == 200

    # 2. Create vehicle with test drive enabled
    brands = client.get(f"/api/v1/dealerships/{dealership_id}/brands", headers=admin_headers)
    brand_id = brands.json()[0]["id"]
    vehicle_res = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=admin_headers,
        json={
            "brand_id": brand_id,
            "model": "FR Test Model",
            "model_year": 2026,
            "price": 30000,
            "stock_number": "FR-016-017",
            "test_drive_enabled": True,
        },
    )
    assert vehicle_res.status_code == 201
    vehicle_id = vehicle_res.json()["id"]

    # 3. Generate slots for next open weekday
    current_day = date.today() + timedelta(days=1)
    while current_day.weekday() > 4:
        current_day += timedelta(days=1)
    test_date = current_day.isoformat()

    slots_gen = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/generate",
        headers=admin_headers,
        params={"start_date": test_date, "end_date": test_date},
    )
    assert slots_gen.status_code == 200
    generated_slots = slots_gen.json()
    assert len(generated_slots) >= 2

    slot1 = generated_slots[0]

    # FR-016: Verify availability fields
    assert slot1["capacity"] == 1
    assert slot1["booked_count"] == 0
    assert slot1["remaining_capacity"] == 1
    assert slot1["is_available"] is True

    # Filter by vehicle_id
    v_slots = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots?vehicle_id={vehicle_id}",
        headers=customer_headers,
    )
    assert v_slots.status_code == 200
    assert all(s["vehicle_id"] == vehicle_id for s in v_slots.json())

    # FR-017: Booking validation - unconfirmed booking must be rejected
    unconfirmed = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot1['id']}/bookings",
        headers=customer_headers,
        json={"confirmed": False},
    )
    assert unconfirmed.status_code == 400
    assert "explicit confirmation" in unconfirmed.json()["detail"].lower()

    # Explicit confirmation succeeds
    booking1 = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot1['id']}/bookings",
        headers=customer_headers,
        json={"confirmed": True},
    )
    assert booking1.status_code == 201
    booking_details = booking1.json()
    assert booking_details["customer_email"] == CUSTOMER_DEMO_EMAIL
    assert booking_details["vehicle_name"] == (
        f"{vehicle_res.json()['model_year']} "
        f"{vehicle_res.json()['make']} {vehicle_res.json()['model']}"
    )
    assert booking_details["starts_at"] == slot1["starts_at"]
    assert booking_details["ends_at"] == slot1["ends_at"]

    lead_path = f"/api/v1/dealerships/{dealership_id}/leads"
    invalid_lead = client.post(
        lead_path,
        json={
            "name": "Demo Customer",
            "email": CUSTOMER_DEMO_EMAIL,
            "message": "Please contact me about this vehicle.",
            "consent_to_contact": False,
        },
    )
    assert invalid_lead.status_code == 422

    lead_response = client.post(
        lead_path,
        headers=customer_headers,
        json={
            "name": "Demo Customer",
            "email": CUSTOMER_DEMO_EMAIL,
            "message": "Please contact me about this vehicle.",
            "source": "assistant",
            "requested_vehicle_id": vehicle_id,
            "consent_to_contact": True,
        },
    )
    assert lead_response.status_code == 201
    lead_id = lead_response.json()["id"]
    assert lead_response.json()["consented_at"] is not None
    assert client.get(lead_path, headers=customer_headers).status_code == 403
    assert client.patch(
        f"{lead_path}/{lead_id}",
        headers=admin_headers,
        json={},
    ).status_code == 400

    assigned_lead = client.patch(
        f"/api/v1/dealerships/{dealership_id}/leads/{lead_id}",
        headers=admin_headers,
        json={
            "status": "qualified",
            "assigned_to_user_id": seeded_users[1].id,
            "next_follow_up_at": "2030-01-02T10:00:00Z",
        },
    )
    assert assigned_lead.status_code == 200
    assert assigned_lead.json()["status"] == "qualified"
    assert assigned_lead.json()["assigned_to_user_id"] == seeded_users[1].id

    converted_lead = client.post(
        f"/api/v1/dealerships/{dealership_id}/leads/{lead_id}/convert",
        headers=admin_headers,
        json={"booking_id": booking1.json()["id"]},
    )
    assert converted_lead.status_code == 200
    assert converted_lead.json()["status"] == "test_drive_scheduled"
    assert converted_lead.json()["test_drive_booking_id"] == booking1.json()["id"]

    # Check slot capacity updated
    slot1_updated = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot1['id']}",
        headers=customer_headers,
    ).json()
    assert slot1_updated["booked_count"] == 1
    assert slot1_updated["remaining_capacity"] == 0
    assert slot1_updated["is_available"] is False

    # FR-017: Double booking prevention - same slot
    double_book = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot1['id']}/bookings",
        headers=customer_headers,
        json={"confirmed": True},
    )
    assert double_book.status_code == 409

    # Filter with available_only=true should NOT include slot1 now
    avail_slots = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots?available_only=true",
        headers=customer_headers,
    ).json()
    slot_ids = [s["id"] for s in avail_slots]
    assert slot1["id"] not in slot_ids


def test_fr018_booking_management_staff_and_customer_verification(
    client, seeded_users
) -> None:
    dealership_id = seeded_users[1].dealership_id

    # 1. Logins
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": DEALERSHIP_DEMO_EMAIL, "password": DEALERSHIP_DEMO_PASSWORD},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    customer_login = client.post(
        "/api/v1/auth/login",
        json={"email": CUSTOMER_DEMO_EMAIL, "password": CUSTOMER_DEMO_PASSWORD},
    )
    customer_headers = {
        "Authorization": f"Bearer {customer_login.json()['access_token']}"
    }

    # 2. Setup vehicle and slots
    brands = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands", headers=admin_headers
    )
    brand_id = brands.json()[0]["id"]
    vehicle_res = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=admin_headers,
        json={
            "brand_id": brand_id,
            "model": "Reschedule Model",
            "model_year": 2026,
            "price": 35000,
            "stock_number": "FR-018-001",
            "test_drive_enabled": True,
        },
    )
    assert vehicle_res.status_code == 201

    current_day = date.today() + timedelta(days=2)
    while current_day.weekday() > 4:
        current_day += timedelta(days=1)
    test_date = current_day.isoformat()

    slots_gen = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/generate",
        headers=admin_headers,
        params={"start_date": test_date, "end_date": test_date},
    )
    slots = slots_gen.json()
    assert len(slots) >= 3
    slot1, slot2, slot3 = slots[0], slots[1], slots[2]

    # Customer books slot1
    booking_res = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot1['id']}/bookings",
        headers=customer_headers,
        json={"confirmed": True},
    )
    assert booking_res.status_code == 201
    booking_id = booking_res.json()["id"]

    # 3. Staff can view bookings across dealership
    staff_bookings = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings",
        headers=admin_headers,
    )
    assert staff_bookings.status_code == 200
    booking_ids = [b["id"] for b in staff_bookings.json()]
    assert booking_id in booking_ids

    # Staff can view single booking details
    staff_booking_detail = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}",
        headers=admin_headers,
    )
    assert staff_booking_detail.status_code == 200
    assert staff_booking_detail.json()["id"] == booking_id

    # 4. Customer-facing rescheduling requires contact verification
    # Mismatched verification email fails
    bad_verify = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}/reschedule",
        headers=customer_headers,
        json={
            "new_slot_id": slot2["id"],
            "verification_email": "wrong-email@example.com",
            "confirmed": True,
        },
    )
    assert bad_verify.status_code == 400
    assert "verification failed" in bad_verify.json()["detail"].lower()

    # Valid customer-facing reschedule succeeds
    reschedule_res = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}/reschedule",
        headers=customer_headers,
        json={
            "new_slot_id": slot2["id"],
            "verification_email": CUSTOMER_DEMO_EMAIL,
            "confirmed": True,
        },
    )
    assert reschedule_res.status_code == 200
    assert reschedule_res.json()["slot_id"] == slot2["id"]

    # Verify slot capacities shifted: slot1 freed, slot2 filled
    s1 = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot1['id']}",
        headers=admin_headers,
    ).json()
    s2 = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot2['id']}",
        headers=admin_headers,
    ).json()
    assert s1["booked_count"] == 0
    assert s2["booked_count"] == 1

    # 5. Staff can reschedule without customer contact verification
    staff_reschedule = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}/reschedule",
        headers=admin_headers,
        json={"new_slot_id": slot3["id"], "confirmed": True},
    )
    assert staff_reschedule.status_code == 200
    assert staff_reschedule.json()["slot_id"] == slot3["id"]

    # 6. Customer-facing cancellation requires contact verification
    bad_cancel = client.delete(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}",
        headers=customer_headers,
        params={"verification_email": "wrong-cancel@example.com"},
    )
    assert bad_cancel.status_code == 400
    assert "verification failed" in bad_cancel.json()["detail"].lower()

    # 7. Authorized staff can cancel bookings
    staff_cancel = client.delete(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}",
        headers=admin_headers,
    )
    assert staff_cancel.status_code == 204

    # Verify booking status cancelled and slot freed
    cancelled_booking = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}",
        headers=admin_headers,
    ).json()
    assert cancelled_booking["status"] == "cancelled"
    assert cancelled_booking["cancelled_at"] is not None

    s3 = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot3['id']}",
        headers=admin_headers,
    ).json()
    assert s3["booked_count"] == 0
