from datetime import date, timedelta

from app.models.user import PasswordResetToken
from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_PASSWORD,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_PASSWORD,
)


def _login(client, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _next_open_weekday() -> date:
    current_day = date.today() + timedelta(days=1)
    while current_day.weekday() > 4:
        current_day += timedelta(days=1)
    return current_day


def test_auth_profile_refresh_reset_and_delete(client, db, monkeypatch) -> None:
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "CRUD User",
            "email": "crud-user@example.com",
            "password": "InitialPassword!1",
        },
    )
    assert signup.status_code == 201
    token_response = client.post(
        "/api/v1/auth/login",
        json={"email": "crud-user@example.com", "password": "InitialPassword!1"},
    )
    refresh_token = token_response.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

    updated = client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"name": "Updated CRUD User"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated CRUD User"
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refreshed.status_code == 200
    rotated_refresh_token = refreshed.json()["refresh_token"]
    assert rotated_refresh_token
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        ).status_code
        == 401
    )

    reset_email = {}

    def send_reset(*, recipient: str, reset_token: str) -> str:
        reset_email["token"] = reset_token
        return "email_sent"

    monkeypatch.setattr("app.services.account_service.send_password_reset", send_reset)
    requested = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "crud-user@example.com"},
    )
    assert requested.status_code == 200
    reset = db.query(PasswordResetToken).one()
    assert reset.token == reset_email["token"]
    confirmed = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset.token, "new_password": "ChangedPassword!1"},
    )
    assert confirmed.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotated_refresh_token},
        ).status_code
        == 401
    )
    fresh_login = client.post(
        "/api/v1/auth/login",
        json={"email": "crud-user@example.com", "password": "ChangedPassword!1"},
    )
    assert fresh_login.status_code == 200
    fresh_headers = {"Authorization": f"Bearer {fresh_login.json()['access_token']}"}
    assert client.delete("/api/v1/auth/me", headers=fresh_headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=fresh_headers).status_code == 401


def test_password_reset_email_failure_does_not_leave_unusable_token(
    client,
    db,
    monkeypatch,
) -> None:
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Reset Failure User",
            "email": "reset-failure@example.com",
            "password": "InitialPassword!1",
        },
    )
    assert signup.status_code == 201
    monkeypatch.setattr(
        "app.services.account_service.send_password_reset",
        lambda **_: "email_provider_pending",
    )

    response = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "reset-failure@example.com"},
    )

    assert response.status_code == 200
    assert db.query(PasswordResetToken).count() == 0


def test_dealership_staff_and_vehicle_crud(client, seeded_users) -> None:
    admin_token = _login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)
    dealership_id = seeded_users[1].dealership_id
    headers = {"Authorization": f"Bearer {admin_token}"}
    brand_id = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
    ).json()[0]["id"]

    dealership = client.get(
        f"/api/v1/dealerships/{dealership_id}",
        headers=headers,
    )
    assert dealership.status_code == 200
    updated_dealership = client.patch(
        f"/api/v1/dealerships/{dealership_id}",
        headers=headers,
        json={"phone": "555-0100"},
    )
    assert updated_dealership.status_code == 200

    invited = client.post(
        f"/api/v1/dealerships/{dealership_id}/staff/invite",
        headers=headers,
        json={
            "name": "CRUD Staff",
            "email": "crud-staff@example.com",
            "role": "sales_rep",
        },
    )
    assert invited.status_code == 201
    staff_id = invited.json()["user_id"]
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/staff",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealership_id/staff/{staff_id}",
            headers=headers,
            json={"name": "Updated Staff"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/staff/{staff_id}",
            headers=headers,
            json={"name": "Updated Staff"},
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/staff/{staff_id}",
            headers=headers,
        ).status_code
        == 204
    )

    vehicle = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=headers,
        json={
            "brand_id": brand_id,
            "model": "Vehicle",
            "model_year": 2026,
            "price": 10000,
            "stock_number": "CRUD-001",
            "test_drive_enabled": True,
        },
    )
    vehicle_id = vehicle.json()["id"]
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=headers,
            json={"price": 11000},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/availability?available=false",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=headers,
        ).status_code
        == 204
    )


def test_test_drive_settings_slots_and_customer_booking(client, seeded_users) -> None:
    admin_token = _login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)
    customer_token = _login(client, CUSTOMER_DEMO_EMAIL, CUSTOMER_DEMO_PASSWORD)
    dealership_id = seeded_users[1].dealership_id
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    brand_id = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=admin_headers,
    ).json()[0]["id"]

    vehicle = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=admin_headers,
        json={
            "brand_id": brand_id,
            "model": "Vehicle",
            "model_year": 2026,
            "price": 10000,
            "stock_number": "BOOK-001",
            "test_drive_enabled": True,
        },
    )
    assert vehicle.status_code == 201
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
            headers=admin_headers,
        ).status_code
        == 200
    )
    generated = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/generate",
        headers=admin_headers,
        params={
            "start_date": _next_open_weekday().isoformat(),
            "end_date": _next_open_weekday().isoformat(),
        },
    )
    assert generated.status_code == 200
    slot_id = generated.json()[0]["id"]
    booking = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings",
        headers=customer_headers,
    )
    assert booking.status_code == 201
    booking_id = booking.json()["id"]
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-bookings",
            headers=customer_headers,
        ).json()[0]["id"]
        == booking_id
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-slots",
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/test-drive-bookings/{booking_id}",
            headers=customer_headers,
        ).status_code
        == 204
    )
