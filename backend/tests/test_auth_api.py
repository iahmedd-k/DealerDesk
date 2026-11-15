from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_PASSWORD,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_PASSWORD,
)


def login(client, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_customer_and_dealership_demo_accounts_can_login(client, seeded_users) -> None:
    customer_token = login(client, CUSTOMER_DEMO_EMAIL, CUSTOMER_DEMO_PASSWORD)
    admin_token = login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)

    customer = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {customer_token}"}
    )
    admin = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert customer.status_code == 200
    assert customer.json()["role"] == "customer"
    assert admin.status_code == 200
    assert admin.json()["role"] == "dealership_admin"


def test_login_rejects_invalid_password(client, seeded_users) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": CUSTOMER_DEMO_EMAIL, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_logout_revokes_token(client, seeded_users) -> None:
    token = login(client, CUSTOMER_DEMO_EMAIL, CUSTOMER_DEMO_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_signup_and_change_password(client) -> None:
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "New Customer",
            "email": "new-customer@example.com",
            "password": "InitialPassword!1",
        },
    )
    assert signup.status_code == 201

    token = login(client, "new-customer@example.com", "InitialPassword!1")
    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "InitialPassword!1",
            "new_password": "ChangedPassword!1",
        },
    )
    assert changed.status_code == 200
    assert login(client, "new-customer@example.com", "ChangedPassword!1")
