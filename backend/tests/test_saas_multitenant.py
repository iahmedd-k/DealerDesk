from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.core.roles import DEALERDESK_ADMIN_ROLE
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_dealerdesk_admin
from app.main import app
from app.models.user import User
from app.models.workspace import Dealership


@pytest.mark.no_db
def test_saas_platform_metrics_and_subscription_flow() -> None:
    client = TestClient(app)

    # 1. Mock Superadmin user
    superadmin = User(
        id=1,
        name="DealerDesk Platform Admin",
        email="dealerdesk@demo.com",
        role=DEALERDESK_ADMIN_ROLE,
        dealership_id=None,
    )

    mock_db = MagicMock()

    # 2. Test metrics endpoint as superadmin
    app.dependency_overrides[require_dealerdesk_admin] = lambda: superadmin
    app.dependency_overrides[get_current_user] = lambda: superadmin
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.dealership_service.get_platform_metrics",
                lambda db: {
                    "total_dealerships": 5,
                    "active_dealerships": 4,
                    "total_mrr": 2495.0,
                    "total_vehicles": 85,
                    "total_bookings": 142,
                    "total_staff": 18,
                    "total_brands": 12,
                    "plan_distribution": {"starter": 1, "pro": 3, "enterprise": 1},
                },
            )
            res = client.get("/api/v1/dealerships/metrics")
            assert res.status_code == 200
            data = res.json()
            assert data["total_dealerships"] == 5
            assert data["total_mrr"] == 2495.0
            assert data["plan_distribution"]["pro"] == 3

        # 3. Test list detailed dealerships as superadmin
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.dealership_service.list_detailed_dealerships",
                lambda db: [
                    {
                        "id": 10,
                        "name": "Apex Motors",
                        "email": "contact@apexmotors.com",
                        "phone": "+1-555-0100",
                        "address": "100 Main St",
                        "timezone": "America/New_York",
                        "is_active": True,
                        "subscription_plan": "pro",
                        "subscription_status": "active",
                        "monthly_price": 499.0,
                        "max_brands": 10,
                        "max_vehicles": 250,
                        "created_at": None,
                        "brands_count": 3,
                        "vehicles_count": 24,
                        "staff_count": 4,
                    }
                ],
            )
            res = client.get("/api/v1/dealerships")
            assert res.status_code == 200
            dealerships = res.json()
            assert len(dealerships) == 1
            assert dealerships[0]["subscription_plan"] == "pro"
            assert dealerships[0]["brands_count"] == 3
            assert dealerships[0]["vehicles_count"] == 24

        # 4. Test subscription update endpoint as superadmin
        updated_dealership = Dealership(
            id=10,
            name="Apex Motors",
            email="contact@apexmotors.com",
            is_active=True,
            subscription_plan="enterprise",
            subscription_status="active",
            monthly_price=Decimal("999.00"),
            max_brands=20,
            max_vehicles=500,
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.dealership_service.update_subscription",
                lambda db, dealership_id, payload: updated_dealership,
            )
            res = client.patch(
                "/api/v1/dealerships/10/subscription",
                json={"subscription_plan": "enterprise", "monthly_price": 999.0},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["subscription_plan"] == "enterprise"
            assert data["monthly_price"] == 999.0

    finally:
        app.dependency_overrides.clear()
