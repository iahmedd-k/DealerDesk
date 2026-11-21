from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models.user import PasswordResetToken
from app.models.workspace import StaffInvitation
from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_PASSWORD,
    DEALERDESK_ADMIN_DEMO_EMAIL,
    DEALERDESK_ADMIN_DEMO_PASSWORD,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_PASSWORD,
)


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _next_open_weekday() -> date:
    current_day = date.today() + timedelta(days=1)
    while current_day.weekday() > 4:
        current_day += timedelta(days=1)
    return current_day


def test_every_api_route_has_a_workflow(client, db, seeded_users, monkeypatch) -> None:
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/health").status_code == 200

    customer_login = _login(client, CUSTOMER_DEMO_EMAIL, CUSTOMER_DEMO_PASSWORD)
    customer_token = customer_login["access_token"]
    admin_login = _login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)
    admin_token = admin_login["access_token"]
    dealerdesk_login = _login(
        client,
        DEALERDESK_ADMIN_DEMO_EMAIL,
        DEALERDESK_ADMIN_DEMO_PASSWORD,
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    dealerdesk_headers = {"Authorization": f"Bearer {dealerdesk_login['access_token']}"}
    dealership_id = seeded_users[1].dealership_id

    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Route Coverage User",
            "email": "route-coverage@example.com",
            "password": "RouteCoverage!1",
        },
    )
    assert signup.status_code == 201
    profile = client.get("/api/v1/auth/me", headers=customer_headers)
    assert profile.status_code == 200
    assert client.get("/api/v1/auth/users", headers=admin_headers).status_code == 200
    assert client.delete("/api/v1/auth/me", headers=admin_headers).status_code == 409
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/staff/{seeded_users[1].id}",
            headers=admin_headers,
            json={"role": "manager"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            "/api/v1/auth/me",
            headers=customer_headers,
            json={"name": "Updated Customer"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/change-password",
            headers=customer_headers,
            json={
                "current_password": CUSTOMER_DEMO_PASSWORD,
                "new_password": "CustomerChanged!1",
            },
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=customer_headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": customer_login["refresh_token"]},
        ).status_code
        == 401
    )
    customer_login = _login(client, CUSTOMER_DEMO_EMAIL, "CustomerChanged!1")
    customer_headers = {"Authorization": f"Bearer {customer_login['access_token']}"}
    reset_email = {}

    def send_reset(*, recipient: str, reset_token: str) -> str:
        reset_email["token"] = reset_token
        return "email_sent"

    monkeypatch.setattr("app.services.account_service.send_password_reset", send_reset)
    reset_request = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "route-coverage@example.com"},
    )
    assert reset_request.status_code == 200
    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == signup.json()["id"]
        )
    )
    assert reset_token is not None
    assert reset_token.token == reset_email["token"]
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token.token, "new_password": "ResetRoute!1"},
        ).status_code
        == 200
    )
    refresh_token = admin_login["refresh_token"]
    first_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert first_refresh.status_code == 200
    rotated_refresh_token = first_refresh.json()["refresh_token"]
    assert rotated_refresh_token
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        ).status_code
        == 401
    )
    second_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated_refresh_token},
    )
    assert second_refresh.status_code == 200
    current_refresh_token = second_refresh.json()["refresh_token"]

    assert client.get("/api/v1/dealerships", headers=dealerdesk_headers).status_code == 200
    assert client.get("/api/v1/dealerships", headers=customer_headers).status_code == 403
    assert client.get(f"/api/v1/dealerships/{dealership_id}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/v1/dealerships/{dealership_id}", headers=customer_headers).status_code == 404
    invalid_timezone_registration = client.post(
        "/api/v1/dealerships/register",
        json={
            "dealership_name": "Invalid Timezone Dealership",
            "dealership_email": "invalid-timezone@example.com",
            "admin_name": "Invalid Timezone Admin",
            "admin_email": "invalid-timezone-admin@example.com",
            "admin_password": "InvalidTimezone!1",
            "timezone": "Not/A_Timezone",
            "brands": ["Toyota"],
        },
    )
    assert invalid_timezone_registration.status_code == 422
    registration = client.post(
        "/api/v1/dealerships/register",
        json={
            "dealership_name": "Route Coverage Dealership",
            "dealership_email": "coverage-dealer@example.com",
            "admin_name": "Coverage Admin",
            "admin_email": "coverage-admin@example.com",
            "admin_password": "CoverageAdmin!1",
            "brands": ["Toyota", "Honda"],
        },
    )
    assert registration.status_code == 201
    new_dealership_id = registration.json()["dealership_id"]
    new_admin_token = _login(
        client,
        "coverage-admin@example.com",
        "CoverageAdmin!1",
    )["access_token"]
    new_admin_headers = {"Authorization": f"Bearer {new_admin_token}"}
    new_brand_id = client.get(
        f"/api/v1/dealerships/{new_dealership_id}/brands",
        headers=new_admin_headers,
    ).json()[0]["id"]
    assert (
        client.patch(
            f"/api/v1/dealerships/{new_dealership_id}",
            headers=new_admin_headers,
            json={"phone": "555-0101"},
        ).status_code
        == 200
    )
    inactive_vehicle = client.post(
        f"/api/v1/dealerships/{new_dealership_id}/vehicles",
        headers=new_admin_headers,
        json={
            "brand_id": new_brand_id,
            "model": "Workspace",
            "model_year": 2026,
            "price": 10000,
            "stock_number": "INACTIVE-001",
            "test_drive_enabled": True,
        },
    )
    assert inactive_vehicle.status_code == 201
    inactive_test_date = _next_open_weekday()
    inactive_slots = client.post(
        f"/api/v1/dealerships/{new_dealership_id}/test-drive-slots/generate",
        headers=new_admin_headers,
        params={
            "start_date": inactive_test_date.isoformat(),
            "end_date": inactive_test_date.isoformat(),
        },
    )
    assert inactive_slots.status_code == 200
    inactive_slot_id = inactive_slots.json()[0]["id"]
    assert (
        client.delete(
            f"/api/v1/dealerships/{new_dealership_id}",
            headers=new_admin_headers,
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{new_dealership_id}/test-drive-slots"
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{new_dealership_id}/test-drive-slots/{inactive_slot_id}/bookings",
            headers=customer_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{new_dealership_id}/vehicles",
            headers=new_admin_headers,
        ).status_code
        == 404
    )

    invitation = client.post(
        f"/api/v1/dealerships/{dealership_id}/staff/invite",
        headers=admin_headers,
        json={
            "name": "Route Coverage Staff",
            "email": "route-staff@example.com",
            "role": "sales_rep",
        },
    )
    assert invitation.status_code == 201
    staff_id = invitation.json()["user_id"]
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/staff",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/staff/{staff_id}",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/staff/{staff_id}",
            headers=admin_headers,
            json={"role": "manager"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/staff/invitations",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/staff/invitations/{invitation.json()['id']}",
            headers=admin_headers,
        ).status_code
        == 204
    )
    old_activation_token = db.get(
        StaffInvitation, invitation.json()["id"]
    ).activation_token
    reinvited = client.post(
        f"/api/v1/dealerships/{dealership_id}/staff/invite",
        headers=admin_headers,
        json={
            "name": "Route Coverage Staff",
            "email": "route-staff@example.com",
            "role": "sales_rep",
        },
    )
    assert reinvited.status_code == 201
    assert reinvited.json()["id"] == invitation.json()["id"]
    activation_record = db.get(StaffInvitation, reinvited.json()["id"])
    assert activation_record is not None
    assert activation_record.activation_token != old_activation_token
    assert (
        client.post(
            "/api/v1/auth/activate-invitation",
            json={"token": old_activation_token, "password": "OldActivation!1"},
        ).status_code
        == 400
    )

    activation_invitation = client.post(
        f"/api/v1/dealerships/{dealership_id}/staff/invite",
        headers=admin_headers,
        json={
            "name": "Activated Staff",
            "email": "activated-staff@example.com",
            "role": "manager",
        },
    )
    activation_record = db.get(StaffInvitation, activation_invitation.json()["id"])
    assert activation_record is not None
    assert (
        client.post(
            "/api/v1/auth/activate-invitation",
            json={
                "token": activation_record.activation_token,
                "password": "Activated!1",
            },
        ).status_code
        == 200
    )

    brand_id = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=admin_headers,
    ).json()[0]["id"]
    vehicle = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=admin_headers,
        json={
            "brand_id": brand_id,
            "model": "Coverage",
            "model_year": 2026,
            "price": 12000,
            "stock_number": "ROUTE-001",
            "test_drive_enabled": True,
        },
    )
    assert vehicle.status_code == 201
    vehicle_id = vehicle.json()["id"]
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/vehicles",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=admin_headers,
            json={"price": 12500},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/availability?available=true",
            headers=admin_headers,
        ).status_code
        == 200
    )

    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
            headers=customer_headers,
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}",
            headers=admin_headers,
            json={"timezone": "America/Los_Angeles"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
            headers=admin_headers,
            json={"opening_time": "09:00", "closing_time": "10:00"},
        ).status_code
        == 200
    )
    test_date = _next_open_weekday()
    generated = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/generate",
        headers=admin_headers,
        params={
            "start_date": test_date.isoformat(),
            "end_date": test_date.isoformat(),
        },
    )
    assert generated.status_code == 200
    old_slot_id = generated.json()[0]["id"]
    updated_settings = client.put(
        f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
        headers=admin_headers,
        json={"opening_time": "10:00", "closing_time": "11:00"},
    )
    assert updated_settings.status_code == 200
    all_slots = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots?include_inactive=true"
    ).json()
    assert (
        next(slot for slot in all_slots if slot["id"] == old_slot_id)["is_active"]
        is False
    )
    active_slots = [slot for slot in all_slots if slot["is_active"]]
    assert active_slots
    slot_id = active_slots[0]["id"]
    local_start = datetime.fromisoformat(active_slots[0]["starts_at"]).astimezone(
        ZoneInfo("America/Los_Angeles")
    )
    assert local_start.hour == 10
    assert (
        client.get(f"/api/v1/dealerships/{dealership_id}/test-drive-slots").status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}"
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}",
            headers=admin_headers,
            json={"is_active": False},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}",
            headers=admin_headers,
            json={"is_active": True},
        ).status_code
        == 200
    )
    booking = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings",
        headers=customer_headers,
    )
    assert booking.status_code == 201
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings",
            headers=customer_headers,
        ).status_code
        == 409
    )
    customer_bookings = client.get(
        f"/api/v1/dealerships/{dealership_id}/test-drive-bookings",
        headers=customer_headers,
    )
    assert customer_bookings.status_code == 200
    assert [item["id"] for item in customer_bookings.json()] == [booking.json()["id"]]
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings",
            headers=customer_headers,
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking.json()['id']}",
            headers=customer_headers,
        ).status_code
        == 204
    )
    replacement_booking = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings",
        headers=customer_headers,
    )
    assert replacement_booking.status_code == 201
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{replacement_booking.json()['id']}",
            headers=customer_headers,
        ).status_code
        == 204
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}",
            headers=admin_headers,
        ).status_code
        == 204
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
            headers=admin_headers,
        ).status_code
        == 204
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=admin_headers,
        ).status_code
        == 204
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/staff/{staff_id}",
            headers=admin_headers,
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/auth/logout",
            headers=admin_headers,
        ).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me", headers=admin_headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": current_refresh_token},
        ).status_code
        == 401
    )
