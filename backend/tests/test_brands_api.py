from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update

from app.services.brand_service import MAX_LOGO_SIZE
from app.core.config import get_settings
from app.db.session import engine
from app.db.migrations import ensure_vehicle_brand_associations
from app.models.workspace import Brand, TestDriveBooking, TestDriveSlot, Vehicle
from app.schemas.workspace import DealershipRegistrationRequest
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


def test_registration_requires_one_to_twenty_unique_brand_names() -> None:
    registration = {
        "dealership_name": "Brand Validation",
        "dealership_email": "brand-validation@example.com",
        "admin_name": "Brand Admin",
        "admin_email": "brand-admin@example.com",
        "admin_password": "Password!123",
    }
    for brands in ([], [" "], ["Toyota", " toyota "], ["Brand"] * 21):
        with pytest.raises(ValidationError):
            DealershipRegistrationRequest.model_validate(
                {**registration, "brands": brands}
            )

    parsed = DealershipRegistrationRequest.model_validate(
        {**registration, "brands": [" Toyota ", "Honda"]}
    )
    assert parsed.brands == ["Toyota", "Honda"]


def test_legacy_vehicle_make_is_backfilled_to_a_brand(db, seeded_users) -> None:
    dealership_id = seeded_users[1].dealership_id
    brand_id = db.scalar(select(Brand.id).where(Brand.dealership_id == dealership_id))
    vehicle = Vehicle(
        dealership_id=dealership_id,
        brand_id=brand_id,
        make="Legacy Make",
        model="Legacy Vehicle",
        model_year=2020,
        price=9000,
        stock_number="LEGACY-BRAND-001",
    )
    db.add(vehicle)
    db.commit()
    vehicle_id = vehicle.id

    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE vehicles DROP COLUMN brand_id CASCADE")
    ensure_vehicle_brand_associations(engine)

    db.expire_all()
    migrated_vehicle = db.get(Vehicle, vehicle_id)
    assert migrated_vehicle is not None
    assert migrated_vehicle.brand_id is not None
    assert migrated_vehicle.make == "Legacy Make"


def test_brand_lifecycle_blocks_inventory_and_preserves_history(
    client,
    db,
    seeded_users,
) -> None:
    dealership_id = seeded_users[1].dealership_id
    admin_headers = {
        "Authorization": f"Bearer {_login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)}"
    }
    customer_headers = {
        "Authorization": f"Bearer {_login(client, CUSTOMER_DEMO_EMAIL, CUSTOMER_DEMO_PASSWORD)}"
    }
    brand = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=admin_headers,
    ).json()[0]
    brand_id = brand["id"]
    vehicle_response = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=admin_headers,
        json={
            "brand_id": brand_id,
            "model": "Test Vehicle",
            "model_year": 2026,
            "price": 12000,
            "stock_number": "BRAND-LIFECYCLE-001",
            "test_drive_enabled": True,
        },
    )
    assert vehicle_response.status_code == 201
    vehicle_id = vehicle_response.json()["id"]
    settings_response = client.put(
        f"/api/v1/dealerships/{dealership_id}/test-drive-settings",
        headers=admin_headers,
        json={"capacity_per_slot": 2},
    )
    assert settings_response.status_code == 200
    test_date = _next_open_weekday().isoformat()
    slots_response = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/generate",
        headers=admin_headers,
        params={"start_date": test_date, "end_date": test_date},
    )
    assert slots_response.status_code == 200
    slot_id = slots_response.json()[0]["id"]
    booking = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings",
        headers=customer_headers,
    )
    assert booking.status_code == 201

    deactivated = client.patch(
        f"/api/v1/dealerships/{dealership_id}/brands/{brand_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/vehicles",
            headers=admin_headers,
        ).json()
        == []
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=admin_headers,
        ).json()["brand_id"]
        == brand_id
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/test-drive-bookings",
            headers=customer_headers,
        ).json()[0]["id"]
        == booking.json()["id"]
    )

    db.execute(
        update(TestDriveSlot).where(TestDriveSlot.id == slot_id).values(is_active=True)
    )
    db.commit()
    blocked_booking = client.post(
        f"/api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings",
        headers=customer_headers,
    )
    assert blocked_booking.status_code == 409
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/availability?available=true",
            headers=admin_headers,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=admin_headers,
            json={"price": 12500},
        ).status_code
        == 200
    )

    db.execute(
        update(TestDriveSlot).where(TestDriveSlot.id == slot_id).values(is_active=False)
    )
    db.commit()
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/availability?available=false",
            headers=admin_headers,
        ).status_code
        == 200
    )
    reactivated = client.patch(
        f"/api/v1/dealerships/{dealership_id}/brands/{brand_id}",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    vehicle = client.get(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
        headers=admin_headers,
    ).json()
    assert vehicle["is_available"] is False
    assert db.get(TestDriveSlot, slot_id).is_active is False

    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/brands/{brand_id}",
            headers=admin_headers,
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/brands/{brand_id}",
            headers=admin_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
            headers=admin_headers,
        ).json()["brand_id"]
        == brand_id
    )
    assert (
        db.scalar(
            select(TestDriveBooking).where(TestDriveBooking.id == booking.json()["id"])
        )
        is not None
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/brands/{brand_id}/restore",
            headers=admin_headers,
        ).json()["is_active"]
        is False
    )


def test_brand_limit_counts_inactive_and_deleted_brands_free_capacity(
    client,
    db,
    seeded_users,
) -> None:
    dealership_id = seeded_users[1].dealership_id
    headers = {
        "Authorization": f"Bearer {_login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)}"
    }
    first_brand_id = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
    ).json()[0]["id"]
    db.add_all(
        Brand(dealership_id=dealership_id, name=f"Brand {index}") for index in range(19)
    )
    db.commit()
    inactive_brand_id = db.scalar(
        select(Brand.id).where(
            Brand.dealership_id == dealership_id,
            Brand.name == "Brand 0",
        )
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/brands",
            headers=headers,
            json={"name": "Beyond Limit"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/brands",
            headers=headers,
            json={"name": " toyota "},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/dealerships/{dealership_id}/brands/{inactive_brand_id}",
            headers=headers,
            json={"is_active": False},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/brands",
            headers=headers,
            json={"name": "Inactive Still Counts"},
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/api/v1/dealerships/{dealership_id}/brands/{inactive_brand_id}",
            headers=headers,
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/brands",
            headers=headers,
            json={"name": "Capacity Reused"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/brands/{inactive_brand_id}/restore",
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.get(
            f"/api/v1/dealerships/{dealership_id}/brands/{first_brand_id}",
            headers=headers,
        ).status_code
        == 200
    )


def test_vehicle_brand_must_be_active_and_owned_by_same_dealership(
    client,
    seeded_users,
) -> None:
    dealership_id = seeded_users[1].dealership_id
    admin_headers = {
        "Authorization": f"Bearer {_login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)}"
    }
    registration = client.post(
        "/api/v1/dealerships/register",
        json={
            "dealership_name": "Second Brand Dealership",
            "dealership_email": "second-brand-dealer@example.com",
            "admin_name": "Second Brand Admin",
            "admin_email": "second-brand-admin@example.com",
            "admin_password": "SecondBrand!123",
            "brands": ["Acura"],
        },
    )
    assert registration.status_code == 201
    other_dealership_id = registration.json()["dealership_id"]
    other_headers = {
        "Authorization": f"Bearer {_login(client, 'second-brand-admin@example.com', 'SecondBrand!123')}"
    }
    other_brand_id = client.get(
        f"/api/v1/dealerships/{other_dealership_id}/brands",
        headers=other_headers,
    ).json()[0]["id"]
    assert (
        client.get(
            f"/api/v1/dealerships/{other_dealership_id}/brands",
            headers=admin_headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/dealerships/{dealership_id}/vehicles",
            headers=admin_headers,
            json={
                "brand_id": other_brand_id,
                "model": "Vehicle",
                "model_year": 2026,
                "price": 10000,
                "stock_number": "CROSS-BRAND-001",
            },
        ).status_code
        == 422
    )


def test_brand_logo_upload_validates_image_and_uses_supabase_storage(
    client,
    seeded_users,
    monkeypatch,
) -> None:
    dealership_id = seeded_users[1].dealership_id
    headers = {
        "Authorization": f"Bearer {_login(client, DEALERSHIP_DEMO_EMAIL, DEALERSHIP_DEMO_PASSWORD)}"
    }
    brand_id = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
    ).json()[0]["id"]

    class Bucket:
        def __init__(self) -> None:
            self.upload_args = None
            self.removed_paths = None

        def upload(self, path, content, options):
            self.upload_args = (path, content, options)

        def get_public_url(self, path):
            return f"https://storage.example/{path}"

        def remove(self, paths):
            self.removed_paths = paths

    class Storage:
        def __init__(self) -> None:
            self.bucket = Bucket()

        def from_(self, bucket_id):
            assert bucket_id == get_settings().supabase_bucket_id
            return self.bucket

    class Client:
        def __init__(self) -> None:
            self.storage = Storage()

    supabase = Client()
    monkeypatch.setattr(
        "app.services.brand_service.get_supabase_client",
        lambda: supabase,
    )
    path = f"/api/v1/dealerships/{dealership_id}/brands/{brand_id}/logo"
    invalid = client.put(
        path,
        headers=headers,
        files={"file": ("logo.png", b"not an image", "image/png")},
    )
    assert invalid.status_code == 422
    uploaded = client.put(
        path,
        headers=headers,
        files={"file": ("logo.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["logo_url"].endswith(f"/brands/{brand_id}/logo")
    assert supabase.storage.bucket.upload_args[2]["upsert"] == "true"
    oversized = client.put(
        path,
        headers=headers,
        files={
            "file": (
                "logo.png",
                b"\x89PNG\r\n\x1a\n" + b"x" * MAX_LOGO_SIZE,
                "image/png",
            )
        },
    )
    assert oversized.status_code == 413
    assert client.delete(path, headers=headers).status_code == 204
    assert supabase.storage.bucket.removed_paths == [
        f"dealerships/{dealership_id}/brands/{brand_id}/logo"
    ]
