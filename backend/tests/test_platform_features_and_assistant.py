from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.models.user import User
from app.schemas.assistant import AssistantChatRequest
from app.services import assistant_service
from seed.demo_credentials import (
    CUSTOMER_DEMO_EMAIL,
    CUSTOMER_DEMO_PASSWORD,
    DEALERSHIP_DEMO_EMAIL,
    DEALERSHIP_DEMO_PASSWORD,
)

pytestmark = pytest.mark.no_db


def test_health_check_deep_diagnostics() -> None:
    client = TestClient(app)
    res = client.get("/api/v1/health")
    assert res.status_code in (200, 503)
    data = res.json()
    assert "status" in data
    assert "timestamp" in data
    assert "database" in data
    assert "services" in data
    assert "storage" in data["services"]
    assert "email" in data["services"]
    assert "llm" in data["services"]


def test_health_check_does_not_expose_database_errors() -> None:
    client = TestClient(app)
    with patch(
        "app.services.health_service.check_database",
        side_effect=SQLAlchemyError("sensitive database details"),
    ):
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["database"]["status"] == "unavailable"
    assert "sensitive database details" not in response.text


def test_correlation_id_middleware() -> None:
    client = TestClient(app)

    # 1. Automatic generation when header is not supplied
    res1 = client.get("/")
    assert res1.status_code == 200
    req_id1 = res1.headers.get("X-Request-ID")
    assert req_id1 is not None
    assert len(req_id1) > 10

    # 2. Propagation when header is provided
    custom_id = "test-custom-correlation-id-9988"
    res2 = client.get("/", headers={"X-Request-ID": custom_id})
    assert res2.status_code == 200
    assert res2.headers.get("X-Request-ID") == custom_id


def test_idempotency_middleware_replay() -> None:
    client = TestClient(app)
    key = "idem-key-test-unit-001"

    with patch("app.services.account_service.login") as mock_login:
        from app.schemas.auth import TokenResponse
        mock_login.return_value = TokenResponse(
            access_token="mock-access-token",
            refresh_token="mock-refresh-token",
            token_type="bearer",
            expires_in=1800,
        )

        # First call with idempotency key
        res1 = client.post(
            "/api/v1/auth/login",
            headers={"Idempotency-Key": key},
            json={"email": "test@example.com", "password": "Password!123"},
        )
        assert res1.status_code == 200
        assert "Idempotent-Replayed" not in res1.headers
        assert mock_login.call_count == 1

        # Second call with the same key replays cached response without invoking login again
        res2 = client.post(
            "/api/v1/auth/login",
            headers={"Idempotency-Key": key},
            json={"email": "test@example.com", "password": "Password!123"},
        )
        assert res2.status_code == 200
        assert res2.headers.get("Idempotent-Replayed") == "true"
        assert res2.json() == res1.json()
        assert mock_login.call_count == 1  # Not invoked again!


def test_structured_error_envelope() -> None:
    client = TestClient(app)
    custom_id = "err-envelope-id-4455"
    res = client.get(
        "/api/v1/dealerships/999999",
        headers={"X-Request-ID": custom_id},
    )
    assert res.status_code == 403
    data = res.json()
    assert "detail" in data
    assert "error_code" in data
    assert data["error_code"] == "FORBIDDEN"
    assert data.get("request_id") == custom_id
    assert "timestamp" in data


def test_dealership_ai_assistant_grounded_response_mock() -> None:
    # Verify the assistant synthesizes context correctly
    mock_db = MagicMock()
    mock_dealership = MagicMock()
    mock_dealership.id = 1
    mock_dealership.name = "Apex Motors"
    mock_dealership.address = "742 Evergreen Terrace"
    mock_dealership.phone = "555-0199"

    with patch("app.repositories.dealership_repository.get_active_by_id", return_value=mock_dealership), \
         patch("app.repositories.test_drive_repository.get_settings", return_value=None), \
         patch("app.repositories.vehicle_repository.list_for_dealership", return_value=[]), \
         patch("app.repositories.test_drive_repository.list_slots", return_value=[]), \
         patch("app.services.knowledge_service.search", return_value=[]):

        # General inquiry
        res_general = assistant_service.chat_with_assistant(
            mock_db,
            1,
            AssistantChatRequest(message="Hello, can you help me?"),
        )
        assert res_general.dealership_id == 1
        assert res_general.dealership_name == "Apex Motors"
        assert "Apex Motors" in res_general.response
        assert res_general.intent == "general"

        # Hours / Info inquiry
        res_hours = assistant_service.chat_with_assistant(
            mock_db,
            1,
            AssistantChatRequest(message="What are your hours and address?"),
        )
        assert res_hours.intent == "dealership_info"
        assert "742 Evergreen Terrace" in res_hours.response

        # Test drive inquiry
        res_td = assistant_service.chat_with_assistant(
            mock_db,
            1,
            AssistantChatRequest(message="I want to book a test drive"),
        )
        assert res_td.intent == "test_drive_booking"
        assert "test drive" in res_td.response.lower()


def test_vehicle_collection_filtering_sorting_and_pagination() -> None:
    client = TestClient(app)
    mock_vehicle = MagicMock()
    mock_vehicle.id = 10
    mock_vehicle.dealership_id = 1
    mock_vehicle.brand_id = 2
    mock_vehicle.make = "Toyota"
    mock_vehicle.model = "Camry"
    mock_vehicle.model_year = 2024
    mock_vehicle.variant = "SE"
    mock_vehicle.description = "Reliable sedan"
    mock_vehicle.price = 28000.0
    mock_vehicle.stock_number = "STK-100"
    mock_vehicle.is_available = True
    mock_vehicle.test_drive_enabled = True
    mock_vehicle.images = []

    with patch("app.services.vehicle_service.list_public_vehicles", return_value=[mock_vehicle]) as mock_list, \
         patch("app.services.vehicle_service.count_vehicles", return_value=15) as mock_count:
        res = client.get(
            "/api/v1/dealerships/1/vehicles/public?page=2&page_size=5&min_price=20000&sort_by=price&order=desc&search=Camry"
        )
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.headers.get("X-Total-Count") == "15"
        assert res.headers.get("X-Page") == "2"
        assert res.headers.get("X-Page-Size") == "5"
        assert res.headers.get("X-Total-Pages") == "3"

        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        assert kwargs["page"] == 2
        assert kwargs["page_size"] == 5
        assert kwargs["min_price"] == 20000.0
        assert kwargs["sort_by"] == "price"
        assert kwargs["order"] == "desc"
        assert kwargs["search"] == "Camry"
