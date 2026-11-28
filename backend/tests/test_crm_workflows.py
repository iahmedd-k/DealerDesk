from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.main import app as fastapi_app
from app.schemas.workspace import (
    BulkCustomerLeadUpdateRequest,
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
    monkeypatch.setattr(lead_service, "notify_new_lead", lambda *a, **_kwargs: None)
    monkeypatch.setattr(lead_service, "_notify_lead_assigned", lambda *a, **_kwargs: None)

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
        lost_reason=None,
        next_follow_up_at=None,
        deal_value=None,
        deal_notes=None,
        updated_at=None,
    )
    staff = SimpleNamespace(id=2, role="manager", dealership_id=1, email="mgr@apex.com")
    activities: list[tuple[str, str]] = []

    monkeypatch.setattr(lead_service.lead_repository, "get_lead", lambda db, did, lid, **_kw: lead)
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


def test_lead_channel_consent_records_opt_in_and_opt_out_activity(monkeypatch) -> None:
    lead = SimpleNamespace(
        id=101,
        dealership_id=1,
        name="Tariq",
        email="tariq@example.com",
        requested_vehicle_id=None,
        test_drive_booking_id=None,
        status="new",
        lost_reason=None,
        assigned_to_user_id=None,
        next_follow_up_at=None,
        email_consent=False,
        email_consented_at=None,
        email_opted_out_at=None,
        sms_consent=False,
        sms_consented_at=None,
        sms_opted_out_at=None,
        whatsapp_consent=False,
        whatsapp_consented_at=None,
        whatsapp_opted_out_at=None,
        updated_at=None,
    )
    staff = SimpleNamespace(id=2, role="manager", dealership_id=1)
    activities: list[dict[str, object]] = []

    monkeypatch.setattr(lead_service.lead_repository, "get_lead", lambda *args, **kwargs: lead)
    monkeypatch.setattr(lead_service.lead_repository, "save", lambda _db, item: item)
    monkeypatch.setattr(
        lead_service,
        "_record_activity",
        lambda _db, **kwargs: activities.append(kwargs),
    )

    opted_in = lead_service.update_lead(
        MagicMock(),
        1,
        101,
        staff,
        CustomerLeadUpdateRequest(email_consent=True),
    )

    assert opted_in.email_consent is True
    assert opted_in.email_consented_at is not None
    assert opted_in.email_opted_out_at is None
    assert activities[-1]["activity_type"] == "consent_updated"
    assert activities[-1]["details"]["status"] == "opted_in"

    opted_out = lead_service.update_lead(
        MagicMock(),
        1,
        101,
        staff,
        CustomerLeadUpdateRequest(email_consent=False),
    )

    assert opted_out.email_consent is False
    assert opted_out.email_consented_at is not None
    assert opted_out.email_opted_out_at is not None
    assert activities[-1]["activity_type"] == "consent_updated"
    assert activities[-1]["details"]["status"] == "opted_out"


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
        email_consent=False,
        email_consented_at=None,
        email_opted_out_at=None,
        sms_consent=False,
        sms_consented_at=None,
        sms_opted_out_at=None,
        whatsapp_consent=False,
        whatsapp_consented_at=None,
        whatsapp_opted_out_at=None,
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


def test_quote_snapshot_is_a_valid_lead_activity() -> None:
    quote_activity = LeadActivityCreateRequest(
        activity_type="quote",
        summary="Deal estimate saved",
        details={"sale_price": 42000, "estimated_monthly_payment": 650},
    )

    assert quote_activity.activity_type == "quote"
    assert quote_activity.details["sale_price"] == 42000


def test_bulk_lead_update_changes_stage_and_assignment_in_one_batch(monkeypatch) -> None:
    lead = SimpleNamespace(
        id=101,
        dealership_id=1,
        status="new",
        deal_value=None,
        assigned_to_user_id=None,
        test_drive_booking_id=None,
        updated_at=None,
        name="Tariq",
        email="tariq@example.com",
        phone=None,
        message="Interested",
        source="website",
        requested_vehicle_id=None,
    )
    manager = SimpleNamespace(id=2, role="manager", dealership_id=1)
    rep = SimpleNamespace(id=3)
    db = MagicMock()
    assignments: list[int] = []
    monkeypatch.setattr(lead_service.lead_repository, "get_staff_user", lambda *args: rep)
    monkeypatch.setattr(lead_service.lead_repository, "get_leads_by_ids", lambda *args: [lead])
    monkeypatch.setattr(
        lead_service,
        "_notify_lead_assigned",
        lambda _db, _dealership_id, assigned, **_kwargs: assignments.append(assigned.id),
    )

    updated = lead_service.bulk_update_leads(
        db,
        1,
        manager,
        BulkCustomerLeadUpdateRequest(
            lead_ids=[101],
            status="contacted",
            assigned_to_user_id=3,
        ),
    )

    assert updated == [lead]
    assert lead.status == "contacted"
    assert lead.assigned_to_user_id == 3
    assert assignments == [101]
    db.commit.assert_called_once()


def test_bulk_lead_update_rejects_invalid_stage_for_booking_linked_lead(monkeypatch) -> None:
    lead = SimpleNamespace(
        id=101,
        dealership_id=1,
        status="test_drive_scheduled",
        assigned_to_user_id=None,
        test_drive_booking_id=22,
        updated_at=None,
    )
    manager = SimpleNamespace(id=2, role="manager", dealership_id=1)
    db = MagicMock()
    monkeypatch.setattr(lead_service.lead_repository, "get_leads_by_ids", lambda *args: [lead])

    with pytest.raises(lead_service.ConflictError):
        lead_service.bulk_update_leads(
            db,
            1,
            manager,
            BulkCustomerLeadUpdateRequest(lead_ids=[101], status="contacted"),
        )
    db.commit.assert_not_called()


def test_csv_lead_import_requires_contact_consent_and_reports_created_rows(monkeypatch) -> None:
    from app.api.v1.endpoints import leads as leads_endpoint
    from app.db.session import get_db
    from app.dependencies.auth import get_current_user

    admin = SimpleNamespace(id=1, role="dealership_admin", dealership_id=1, is_active=True)
    created_leads: list[str] = []
    monkeypatch.setattr(
        lead_service,
        "create_lead",
        lambda _db, _dealership_id, payload, _user, **_kwargs: (
            created_leads.append(payload.email)
            or SimpleNamespace(id=len(created_leads), source=payload.source)
        ),
    )
    monkeypatch.setattr(
        leads_endpoint.audit_service,
        "log_event",
        lambda *args, **kwargs: None,
    )
    fastapi_app.dependency_overrides[get_current_user] = lambda: admin
    fastapi_app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        with TestClient(fastapi_app) as client:
            response = client.post(
                "/api/v1/dealerships/1/leads/import",
                json={
                    "csv_content": (
                        "name,email,message,consent_to_contact\n"
                        "No Consent,no@example.com,Asked about a vehicle,false\n"
                        "Yes Consent,yes@example.com,Asked about a vehicle,true\n"
                    )
                },
            )
        assert response.status_code == 200
        assert response.json() == {
            "created": 1,
            "failed": 1,
            "errors": [{"row": 2, "error": "Contact consent must be explicitly true"}],
        }
        assert created_leads == ["yes@example.com"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_lead_csv_export_includes_structured_deal_terms(monkeypatch) -> None:
    import csv
    from io import StringIO

    from app.api.v1.endpoints import leads as leads_endpoint

    lead = SimpleNamespace(
        id=101,
        name="Tariq",
        email="tariq@example.com",
        phone=None,
        message="Interested in a vehicle",
        source="website",
        status="qualified",
        lost_reason=None,
        email_consent=False,
        email_consented_at=None,
        email_opted_out_at=None,
        sms_consent=False,
        sms_consented_at=None,
        sms_opted_out_at=None,
        whatsapp_consent=False,
        whatsapp_consented_at=None,
        whatsapp_opted_out_at=None,
        assigned_to_user_id=None,
        next_follow_up_at=None,
        budget=Decimal("0"),
        purchase_timeline=None,
        deal_value=Decimal("0"),
        deal_notes=None,
        trade_in_vehicle="2018 Sedan",
        trade_in_value=Decimal("5000"),
        down_payment=Decimal("0"),
        apr_percent=Decimal("4.25"),
        loan_term_months=60,
    )
    monkeypatch.setattr(lead_service, "list_leads", lambda *args, **kwargs: [lead])

    response = leads_endpoint.export_leads_to_csv(
        dealership_id=1,
        current_user=SimpleNamespace(),
        db=MagicMock(),
    )
    rows = list(csv.DictReader(StringIO(response.body.decode("utf-8"))))

    assert rows == [
        {
            "id": "101",
            "name": "Tariq",
            "email": "tariq@example.com",
            "phone": "",
            "message": "Interested in a vehicle",
            "source": "website",
            "status": "qualified",
            "lost_reason": "",
            "email_consent": "False",
            "email_consented_at": "",
            "email_opted_out_at": "",
            "sms_consent": "False",
            "sms_consented_at": "",
            "sms_opted_out_at": "",
            "whatsapp_consent": "False",
            "whatsapp_consented_at": "",
            "whatsapp_opted_out_at": "",
            "assigned_to_user_id": "",
            "next_follow_up_at": "",
            "budget": "0",
            "purchase_timeline": "",
            "deal_value": "0",
            "deal_notes": "",
            "trade_in_vehicle": "2018 Sedan",
            "trade_in_value": "5000",
            "down_payment": "0",
            "apr_percent": "4.25",
            "loan_term_months": "60",
        }
    ]
