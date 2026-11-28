from seed.demo_credentials import DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD


def _admin_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": DEALERSHIP_DEMO_EMAIL,
            "password": DEALERSHIP_DEMO_PASSWORD,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_lead_quotes_are_versioned_and_have_a_status_lifecycle(
    client,
    seeded_users,
) -> None:
    _, admin, _ = seeded_users
    headers = _admin_headers(client)
    lead_response = client.post(
        f"/api/v1/dealerships/{admin.dealership_id}/leads",
        headers=headers,
        json={
            "name": "Quote Customer",
            "email": "quote-customer@example.com",
            "message": "Interested in financing",
            "source": "phone",
            "consent_to_contact": True,
        },
    )
    assert lead_response.status_code == 201
    lead_id = lead_response.json()["id"]
    quote_url = f"/api/v1/dealerships/{admin.dealership_id}/leads/{lead_id}/quotes"

    quote_payload = {
        "vehicle_label": "2025 Example Sedan",
        "sale_price": "30000.00",
        "trade_in_vehicle": "2018 Example Coupe",
        "trade_in_value": "2000.00",
        "down_payment": "3000.00",
        "apr_percent": "6.00",
        "loan_term_months": 60,
    }
    first_response = client.post(quote_url, headers=headers, json=quote_payload)
    assert first_response.status_code == 201
    first_quote = first_response.json()
    assert first_quote["version"] == 1
    assert first_quote["amount_financed"] == 25000
    assert first_quote["estimated_monthly_payment"] > 0
    assert first_quote["disclaimer"].startswith("Estimate only")

    overfinanced_response = client.post(
        quote_url,
        headers=headers,
        json={
            **quote_payload,
            "sale_price": "4000.00",
            "trade_in_value": "2000.00",
            "down_payment": "3000.00",
        },
    )
    assert overfinanced_response.status_code == 400

    second_response = client.post(
        quote_url,
        headers=headers,
        json={**quote_payload, "sale_price": "31000.00"},
    )
    assert second_response.status_code == 201
    assert second_response.json()["version"] == 2

    sent_response = client.patch(
        f"{quote_url}/{first_quote['id']}",
        headers=headers,
        json={"status": "sent"},
    )
    assert sent_response.status_code == 200
    accepted_response = client.patch(
        f"{quote_url}/{first_quote['id']}",
        headers=headers,
        json={"status": "accepted"},
    )
    assert accepted_response.status_code == 200
    assert accepted_response.json()["status"] == "accepted"
    assert client.patch(
        f"{quote_url}/{first_quote['id']}",
        headers=headers,
        json={"status": "sent"},
    ).status_code == 409

    listed = client.get(quote_url, headers=headers)
    assert listed.status_code == 200
    assert [item["version"] for item in listed.json()] == [2, 1]

    activities = client.get(
        f"/api/v1/dealerships/{admin.dealership_id}/leads/{lead_id}/activities",
        headers=headers,
    )
    assert activities.status_code == 200
    assert any(item["activity_type"] == "quote" for item in activities.json())

    lost_response = client.patch(
        f"/api/v1/dealerships/{admin.dealership_id}/leads/{lead_id}",
        headers=headers,
        json={"status": "lost", "lost_reason": "price"},
    )
    assert lost_response.status_code == 200
    assert lost_response.json()["lost_reason"] == "price"
