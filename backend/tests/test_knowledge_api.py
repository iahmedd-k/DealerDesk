from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

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


def _pdf_with_text(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 10 50 Td ({escaped_text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_staff_can_upload_search_and_delete_brand_scoped_pdf(
    client,
    seeded_users,
) -> None:
    dealership_id = seeded_users[1].dealership_id
    headers = {
        "Authorization": (
            "Bearer "
            + _login(
                client,
                DEALERSHIP_DEMO_EMAIL,
                DEALERSHIP_DEMO_PASSWORD,
            )
        )
    }
    brands = client.get(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
    )
    assert brands.status_code == 200
    brand_id = brands.json()[0]["id"]

    upload = client.post(
        f"/api/v1/dealerships/{dealership_id}/knowledge/documents",
        headers=headers,
        data={"brand_id": str(brand_id)},
        files={
            "file": (
                "vehicle-guide.pdf",
                _pdf_with_text("Hybrid battery warranty lasts eight years."),
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 201
    document = upload.json()
    assert document["brand_id"] == brand_id
    assert document["filename"] == "vehicle-guide.pdf"
    assert document["page_count"] == 1
    assert document["chunk_count"] == 1

    matching = client.post(
        f"/api/v1/dealerships/{dealership_id}/knowledge/search",
        headers=headers,
        json={"query": "hybrid battery warranty", "brand_id": brand_id},
    )
    assert matching.status_code == 200
    assert matching.json()[0]["document_id"] == document["id"]
    assert matching.json()[0]["page_number"] == 1
    assert "eight years" in matching.json()[0]["content"]

    unscoped = client.post(
        f"/api/v1/dealerships/{dealership_id}/knowledge/search",
        headers=headers,
        json={"query": "hybrid battery warranty"},
    )
    assert unscoped.status_code == 200
    assert unscoped.json() == []

    other_brand = client.post(
        f"/api/v1/dealerships/{dealership_id}/brands",
        headers=headers,
        json={"name": "Other Brand"},
    )
    assert other_brand.status_code == 201
    other_results = client.post(
        f"/api/v1/dealerships/{dealership_id}/knowledge/search",
        headers=headers,
        json={"query": "hybrid battery warranty", "brand_id": other_brand.json()["id"]},
    )
    assert other_results.status_code == 200
    assert other_results.json() == []

    text_upload = client.post(
        f"/api/v1/dealerships/{dealership_id}/knowledge/documents",
        headers=headers,
        files={
            "file": (
                "customer-hours.txt",
                b"Customer service hours are nine to five on weekdays.",
                "text/plain",
            )
        },
    )
    assert text_upload.status_code == 201
    global_results = client.post(
        f"/api/v1/dealerships/{dealership_id}/knowledge/search",
        headers=headers,
        json={"query": "customer service hours", "brand_id": brand_id},
    )
    assert global_results.status_code == 200
    assert global_results.json()[0]["document_id"] == text_upload.json()["id"]
    assert global_results.json()[0]["page_number"] is None

    deleted = client.delete(
        f"/api/v1/dealerships/{dealership_id}/knowledge/documents/{document['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    text_deleted = client.delete(
        f"/api/v1/dealerships/{dealership_id}/knowledge/documents/{text_upload.json()['id']}",
        headers=headers,
    )
    assert text_deleted.status_code == 204
    listed = client.get(
        f"/api/v1/dealerships/{dealership_id}/knowledge/documents",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json() == []


def test_customer_cannot_upload_dealership_knowledge(client, seeded_users) -> None:
    dealership_id = seeded_users[1].dealership_id
    customer_headers = {
        "Authorization": (
            "Bearer "
            + _login(
                client,
                CUSTOMER_DEMO_EMAIL,
                CUSTOMER_DEMO_PASSWORD,
            )
        )
    }
    response = client.post(
        f"/api/v1/dealerships/{dealership_id}/knowledge/documents",
        headers=customer_headers,
        files={"file": ("notes.txt", b"Private staff knowledge.", "text/plain")},
    )
    assert response.status_code == 403

    staff_headers = {
        "Authorization": (
            "Bearer "
            + _login(
                client,
                DEALERSHIP_DEMO_EMAIL,
                DEALERSHIP_DEMO_PASSWORD,
            )
        )
    }
    cross_dealership = client.get(
        f"/api/v1/dealerships/{dealership_id + 1}/knowledge/documents",
        headers=staff_headers,
    )
    assert cross_dealership.status_code == 404
