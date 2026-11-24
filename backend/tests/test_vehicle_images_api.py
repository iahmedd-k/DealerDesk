from app.core.config import get_settings
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


def test_staff_can_upload_reorder_and_delete_vehicle_images(
    client,
    seeded_users,
    monkeypatch,
) -> None:
    dealership_id = seeded_users[1].dealership_id
    headers = {"Authorization": f"Bearer {_login(client)}"}
    brand = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
    ).json()[0]
    vehicle_response = client.post(
        f"/api/v1/dealerships/{dealership_id}/vehicles",
        headers=headers,
        json={
            "brand_id": brand["id"],
            "model": "Image Test Vehicle",
            "model_year": 2026,
            "price": 25000,
            "stock_number": "IMAGE-TEST-001",
        },
    )
    assert vehicle_response.status_code == 201
    vehicle_id = vehicle_response.json()["id"]

    class Bucket:
        def __init__(self) -> None:
            self.uploads = {}
            self.removed = []

        def upload(self, path, content, options):
            self.uploads[path] = (content, options)

        def get_public_url(self, path):
            return f"https://storage.example/{path}"

        def remove(self, paths):
            self.removed.extend(paths)

    class Storage:
        def __init__(self) -> None:
            self.bucket = Bucket()

        def from_(self, bucket_id):
            assert bucket_id == get_settings().vehicle_images_bucket_id
            return self.bucket

    class Client:
        def __init__(self) -> None:
            self.storage = Storage()

    supabase = Client()
    monkeypatch.setattr(
        "app.services.vehicle_image_service.get_supabase_client",
        lambda: supabase,
    )
    path = f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}/images"

    invalid = client.post(
        path,
        headers=headers,
        files={"file": ("bad.png", b"not png", "image/png")},
    )
    assert invalid.status_code == 422

    first = client.post(
        path,
        headers=headers,
        data={"alt_text": "Front view"},
        files={"file": ("front.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )
    second = client.post(
        path,
        headers=headers,
        data={"alt_text": "Side view"},
        files={"file": ("side.jpg", b"\xff\xd8\xffimage", "image/jpeg")},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["position"] == 0
    assert second.json()["position"] == 1
    assert first.json()["public_url"].startswith("https://storage.example/")
    assert len(supabase.storage.bucket.uploads) == 2

    moved = client.patch(
        f"{path}/{second.json()['id']}",
        headers=headers,
        json={"position": 0},
    )
    assert moved.status_code == 200
    assert moved.json()["position"] == 0

    vehicle = client.get(
        f"/api/v1/dealerships/{dealership_id}/vehicles/{vehicle_id}",
        headers=headers,
    )
    assert vehicle.status_code == 200
    assert [image["id"] for image in vehicle.json()["images"]] == [
        second.json()["id"],
        first.json()["id"],
    ]

    deleted = client.delete(
        f"{path}/{second.json()['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    images = client.get(path, headers=headers)
    assert images.status_code == 200
    assert [(image["id"], image["position"]) for image in images.json()] == [
        (first.json()["id"], 0)
    ]
    second_path = next(
        object_path
        for object_path, (content, _) in supabase.storage.bucket.uploads.items()
        if content == b"\xff\xd8\xffimage"
    )
    assert supabase.storage.bucket.removed == [second_path]
