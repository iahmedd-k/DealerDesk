from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.main import app as fastapi_app
from app.schemas.workspace import (
    CustomerLeadCreateRequest,
    CustomerLeadUpdateRequest,
    LeadActivityCreateRequest,
)
from app.services import lead_service, retention_service

pytestmark = pytest.mark.no_db


def test_lead_capture_with_budget_timeline_preferences_and_auto_assign(monkeypatch) -> None:
    rep = SimpleNamespace(id=12, name="Rep Ali", email="ali@apex.com")
    recorded_activities: list[tuple[str, str]] = []

    monkeypatch.setattr(lead_service.assistant_service, "validate_assistant_scope", lambda *a: None)
    monkeypatch.setattr(lead_service.lead_repository, "get_vehicle", lambda db, did, vid: SimpleNamespace(id=vid))
    monkeypatch.setattr(lead_service.lead_repository, "find_least_loaded_sales_rep", lambda db, did: rep)
    monkeypatch.setattr(lead_service, "notify_new_lead", lambda *a: None)
    monkeypatch.setattr(lead_service, "_notify_lead_assigned", lambda *a: None)

    def fake_save(db, lead):
        lead.id = 101
        return lead

    monkeypatch.setattr(lead_service.lead_repository, "save", fake_save)
    monkeypatch.setattr(
        lead_service,
        "_record_activity",
        lambda db, **kw: recorded_activities.append((kw["activity_type"], kw["summary"])),
    )

    payload = CustomerLeadCreateRequest(
        name="Tariq",
        email="tariq@example.com",
        phone="555-0199",
        message="Looking for a hybrid SUV",
        source="whatsapp",
        requested_vehicle_id=5,
        consent_to_contact=True,
        budget=Decimal("42000.00"),
        purchase_timeline="this_month",
        conversation_id=33,
        preferences={"fuel_type": "hybrid", "color": "silver"},
        auto_assign=True,
    )

    created = lead_service.create_lead(MagicMock(), 1, payload, None)

    assert created.budget == Decimal("42000.00")
    assert created.purchase_timeline == "this_month"
    assert created.conversation_id == 33
    assert created.preferences == {"fuel_type": "hybrid", "color": "silver"}
    assert created.assigned_to_user_id == 12
    assert [a[0] for a in recorded_activities] == ["created", "assigned"]


def test_lead_deal_update_and_activity_timeline(monkeypatch) -> None:
    lead = SimpleNamespace(
        id=101,
        dealership_id=1,
        name="Tariq",
        email="tariq@example.com",
        phone="555-0199",
        message="Looking for hybrid",
        source="whatsapp",
        requested_vehicle_id=None,
        assigned_to_user_id=None,
        test_drive_booking_id=None,
        status="qualified",
        next_follow_up_at=None,
        deal_value=None,
        deal_notes=None,
        updated_at=None,
    )
    staff = SimpleNamespace(id=2, role="manager", dealership_id=1, email="mgr@apex.com")
    activities: list[tuple[str, str]] = []

    monkeypatch.setattr(lead_service.lead_repository, "get_lead", lambda db, did, lid: lead)
    monkeypatch.setattr(lead_service.lead_repository, "save", lambda db, obj: obj)
    monkeypatch.setattr(
        lead_service,
        "_record_activity",
        lambda db, **kw: activities.append((kw["activity_type"], kw["summary"])),
    )

    update_payload = CustomerLeadUpdateRequest(
        deal_value=Decimal("39500.00"),
        deal_notes="Includes 3-year maintenance",
    )
    updated = lead_service.update_lead(MagicMock(), 1, 101, staff, update_payload)
    assert updated.deal_value == Decimal("39500.00")
    assert updated.deal_notes == "Includes 3-year maintenance"
    assert activities == [("deal_updated", "Deal details updated")]

    monkeypatch.setattr(
        lead_service.lead_repository,
        "save_activity",
        lambda db, act: SimpleNamespace(
            id=1,
            dealership_id=act.dealership_id,
            lead_id=act.lead_id,
            actor_user_id=act.actor_user_id,
            activity_type=act.activity_type,
            summary=act.summary,
            details=act.details,
            created_at=act.created_at,
        ),
    )
    note = lead_service.add_lead_activity(
        MagicMock(),
        1,
        101,
        staff,
        LeadActivityCreateRequest(activity_type="call", summary="Spoke about financing"),
    )
    assert note.activity_type == "call"
    assert note.summary == "Spoke about financing"


def test_leads_endpoint_returns_shared_pagination_headers(monkeypatch) -> None:
    from app.db.session import get_db
    from app.dependencies.auth import get_current_user

    admin = SimpleNamespace(id=1, role="dealership_admin", dealership_id=1, is_active=True)
    now = datetime.now(timezone.utc)
    sample_lead = SimpleNamespace(
        id=1,
        dealership_id=1,
        customer_id=None,
        requested_vehicle_id=None,
        assigned_to_user_id=None,
        test_drive_booking_id=None,
        name="Tariq",
        email="tariq@example.com",
        phone=None,
        message="Hi",
        source="website",
        status="new",
        consent_to_contact=True,
        consented_at=now,
        next_follow_up_at=None,
        budget=40000.0,
        purchase_timeline="immediate",
        conversation_id=None,
        preferences=None,
        deal_value=None,
        deal_notes=None,
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr(lead_service, "list_leads", lambda *a, **kw: [sample_lead])
    monkeypatch.setattr(lead_service, "count_leads", lambda *a, **kw: 25)

    fastapi_app.dependency_overrides[get_current_user] = lambda: admin
    fastapi_app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        with TestClient(fastapi_app) as client:
            res = client.get("/api/v1/dealerships/1/leads?page=2&page_size=10")
            assert res.status_code == 200
            assert res.headers["X-Total-Count"] == "25"
            assert res.headers["X-Page"] == "2"
            assert res.headers["X-Page-Size"] == "10"
            assert res.headers["X-Total-Pages"] == "3"
            body = res.json()
            assert len(body) == 1
            assert body[0]["budget"] == 40000.0
            assert body[0]["purchase_timeline"] == "immediate"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_retention_cleanup_includes_customer_leads() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 2
    result = retention_service.cleanup_expired_data(db, dry_run=True, lead_retention_days=180)
    assert "customer_leads" in result["cleaned_counts"]
    assert result["cleaned_counts"]["customer_leads"] == 2
