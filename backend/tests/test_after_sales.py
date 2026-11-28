from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models.workspace import Brand, Vehicle
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


def test_after_sales_appointment_work_order_follow_up_and_warranty(
    client,
    db,
    seeded_users,
) -> None:
    _, admin, _ = seeded_users
    headers = _admin_headers(client)
    brand = db.scalar(
        select(Brand).where(Brand.dealership_id == admin.dealership_id)
    )
    assert brand is not None
    vehicle = Vehicle(
        dealership_id=admin.dealership_id,
        brand_id=brand.id,
        make=brand.name,
        model="Service Test Vehicle",
        model_year=2025,
        price=25000,
        stock_number="SERVICE-TEST-1",
        is_available=False,
        status="sold",
        test_drive_enabled=False,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    appointment_response = client.post(
        f"/api/v1/dealerships/{admin.dealership_id}/service-appointments",
        headers=headers,
        json={
            "vehicle_id": vehicle.id,
            "customer_name": "Service Customer",
            "customer_email": "service-customer@example.com",
            "customer_phone": "+15555550123",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "concern": "Routine maintenance",
        },
    )
    assert appointment_response.status_code == 201
    appointment = appointment_response.json()
    assert appointment["status"] == "scheduled"

    completed_appointment = client.patch(
        f"/api/v1/dealerships/{admin.dealership_id}/service-appointments/{appointment['id']}",
        headers=headers,
        json={"status": "confirmed"},
    )
    assert completed_appointment.status_code == 200
    completed_appointment = client.patch(
        f"/api/v1/dealerships/{admin.dealership_id}/service-appointments/{appointment['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed_appointment.status_code == 200
    assert completed_appointment.json()["completed_at"] is not None

    follow_up_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    work_order_response = client.post(
        f"/api/v1/dealerships/{admin.dealership_id}/service-work-orders",
        headers=headers,
        json={
            "appointment_id": appointment["id"],
            "vehicle_id": vehicle.id,
            "customer_name": "Ignored snapshot",
            "concern": "Routine maintenance",
            "labor_cost": "100.00",
            "parts_cost": "35.50",
            "follow_up_at": follow_up_at,
        },
    )
    assert work_order_response.status_code == 201
    work_order = work_order_response.json()
    assert work_order["customer_name"] == "Service Customer"
    assert work_order["total_cost"] == 135.5
    assert work_order["follow_up_status"] == "pending"

    due_response = client.get(
        f"/api/v1/dealerships/{admin.dealership_id}/service-work-orders?follow_up_due=true",
        headers=headers,
    )
    assert due_response.status_code == 200
    assert [item["id"] for item in due_response.json()] == [work_order["id"]]

    completed_work_order = client.patch(
        f"/api/v1/dealerships/{admin.dealership_id}/service-work-orders/{work_order['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed_work_order.status_code == 200
    assert completed_work_order.json()["completed_at"] is not None
    follow_up_completed = client.patch(
        f"/api/v1/dealerships/{admin.dealership_id}/service-work-orders/{work_order['id']}",
        headers=headers,
        json={"follow_up_status": "completed"},
    )
    assert follow_up_completed.status_code == 200
    assert follow_up_completed.json()["follow_up_status"] == "completed"

    warranty_response = client.post(
        f"/api/v1/dealerships/{admin.dealership_id}/vehicle-warranties",
        headers=headers,
        json={
            "vehicle_id": vehicle.id,
            "provider": "Dealer warranty",
            "coverage": "Powertrain",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=365)).isoformat(),
            "mileage_limit": 60000,
        },
    )
    assert warranty_response.status_code == 201
    assert warranty_response.json()["is_active"] is True
