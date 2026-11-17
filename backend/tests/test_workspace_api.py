from seed.demo_credentials import DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD


def test_customer_cannot_create_dealership_vehicle(client, seeded_users) -> None:
    customer_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "customer-demo@dealerdesk.dev",
            "password": "DealerDeskCustomer!2026",
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


def test_dealership_admin_can_manage_vehicle_and_settings(client, seeded_users) -> None:
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
            "price": 10000,
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
    assert settings.status_code == 200
