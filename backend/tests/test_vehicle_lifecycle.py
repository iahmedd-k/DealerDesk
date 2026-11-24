import pytest
from seed.demo_credentials import DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD


def _login(client) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": DEALERSHIP_DEMO_EMAIL,
            "password": DEALERSHIP_DEMO_PASSWORD,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_comprehensive_vehicle_lifecycle_transitions_and_history(
    client,
    seeded_users,
) -> None:
    """End-to-end verification of vehicle lifecycle states, transitions, history, and filtering."""
    dealership_id = seeded_users[1].dealership_id
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    brands = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
    ).json()
    brand_id = brands[0]["id"]

    # 1. Creation with default status
    create_res = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=headers,
        json={
            "brand_id": brand_id,
            "model": "Camry Hybrid",
            "model_year": 2025,
            "price": 32000,
            "stock_number": "STK-CAM-001",
            "test_drive_enabled": True,
        },
    )
    assert create_res.status_code == 201
    vehicle = create_res.json()
    assert vehicle["status"] == "available"
    assert vehicle["is_available"] is True
    vehicle_id = vehicle["id"]

    # 2. Verify initial history entry was created
    history_res = client.get(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/history",
        headers=headers,
    )
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 1
    assert history[0]["previous_status"] == "none"
    assert history[0]["new_status"] == "available"
    assert "creation" in history[0]["notes"].lower()

    # 3. Transition 1: available -> reserved
    patch_res = client.patch(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/status",
        headers=headers,
        json={
            "status": "reserved",
            "notes": "Customer deposit placed by John Doe",
        },
    )
    assert patch_res.status_code == 200
    v1 = patch_res.json()
    assert v1["status"] == "reserved"
    assert v1["is_available"] is False

    # 4. Transition 2: reserved -> sold (must also disable test drive)
    patch_res2 = client.patch(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/status",
        headers=headers,
        json={
            "status": "sold",
            "notes": "Purchase completed and financing approved",
        },
    )
    assert patch_res2.status_code == 200
    v2 = patch_res2.json()
    assert v2["status"] == "sold"
    assert v2["is_available"] is False
    assert v2["test_drive_enabled"] is False

    # 5. Transition 3: sold -> available (relisted vehicle)
    patch_res3 = client.patch(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/status",
        headers=headers,
        json={
            "status": "available",
            "notes": "Deal cancelled, vehicle returned to inventory",
        },
    )
    assert patch_res3.status_code == 200
    v3 = patch_res3.json()
    assert v3["status"] == "available"
    assert v3["is_available"] is True

    # 6. Verify full history sequence
    history_res2 = client.get(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/history",
        headers=headers,
    )
    assert history_res2.status_code == 200
    hist = history_res2.json()
    assert len(hist) == 4
    # Ordered descending
    assert hist[0]["previous_status"] == "sold" and hist[0]["new_status"] == "available"
    assert hist[1]["previous_status"] == "reserved" and hist[1]["new_status"] == "sold"
    assert hist[2]["previous_status"] == "available" and hist[2]["new_status"] == "reserved"
    assert hist[3]["previous_status"] == "none" and hist[3]["new_status"] == "available"

    # 7. Create another vehicle in reserved state and test status filtering
    client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=headers,
        json={
            "brand_id": brand_id,
            "model": "RAV4 Prime",
            "model_year": 2025,
            "price": 42000,
            "stock_number": "STK-RAV-RES",
            "status": "reserved",
        },
    )

    # Filter available: should contain CAM-001, but not RAV-RES
    res_avail = client.get(
        f"/api/v1/dealerships/{dealership_id}/vehicles?status=available",
        headers=headers,
    )
    assert res_avail.status_code == 200
    avail_stocks = [v["stock_number"] for v in res_avail.json()]
    assert "STK-CAM-001" in avail_stocks
    assert "STK-RAV-RES" not in avail_stocks

    # Filter reserved: should contain RAV-RES, but not CAM-001
    res_reserved = client.get(
        f"/api/v1/dealerships/{dealership_id}/vehicles?status=reserved",
        headers=headers,
    )
    assert res_reserved.status_code == 200
    reserved_stocks = [v["stock_number"] for v in res_reserved.json()]
    assert "STK-RAV-RES" in reserved_stocks
    assert "STK-CAM-001" not in reserved_stocks

    # 8. Invalid status rejection
    bad_res = client.patch(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/status",
        headers=headers,
        json={"status": "invalid_lifecycle_state"},
    )
    assert bad_res.status_code == 422

    # 9. Availability toggle synchronization
    toggle_res = client.patch(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/availability?available=false",
        headers=headers,
    )
    assert toggle_res.status_code == 200
    toggled = toggle_res.json()
    assert toggled["status"] == "unavailable"
    assert toggled["is_available"] is False

    toggle_res2 = client.patch(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/availability?available=true",
        headers=headers,
    )
    assert toggle_res2.status_code == 200
    toggled2 = toggle_res2.json()
    assert toggled2["status"] == "available"
    assert toggled2["is_available"] is True
