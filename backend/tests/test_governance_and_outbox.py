from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.api.v1.endpoints import governance as governance_ep
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import app as fastapi_app
from app.services import outbox_service

pytestmark = pytest.mark.no_db


def test_outbox_enqueue_and_dispatch_with_retry_and_success(monkeypatch) -> None:
    db = MagicMock()
    event = outbox_service.enqueue_event(
        db,
        dealership_id=1,
        event_type="lead.won",
        aggregate_type="customer_lead",
        aggregate_id=42,
        payload={"lead_id": 42, "deal_value": 35000},
        target_webhook_url="https://hooks.example.com/dealerdesk",
    )
    assert event.status == "pending"
    assert event.event_type == "lead.won"
    db.add.assert_called_once()
    db.commit.assert_called_once()

    # Dispatch success
    delivered_urls: list[str] = []
    monkeypatch.setattr(
        outbox_service,
        "_deliver_webhook",
        lambda url, ev, signing_secret=None: delivered_urls.append(url),
    )
    db2 = MagicMock()
    db2.scalars.return_value = [event]
    report = outbox_service.dispatch_pending_outbox_events(db2, dealership_id=1)

    assert report["delivered"] == 1
    assert report["failed"] == 0
    assert event.status == "delivered"
    assert event.delivered_at is not None
    assert delivered_urls == ["https://hooks.example.com/dealerdesk"]

    # Dispatch failure -> retries then marks failed at MAX_OUTBOX_ATTEMPTS
    failing_event = SimpleNamespace(
        id=2,
        dealership_id=1,
        event_type="vehicle.sold",
        aggregate_type="vehicle",
        aggregate_id="10",
        payload={},
        target_webhook_url="https://hooks.example.com/fail",
        status="pending",
        attempts=outbox_service.MAX_OUTBOX_ATTEMPTS - 1,
        last_error=None,
        next_retry_at=None,
        delivered_at=None,
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        outbox_service,
        "_deliver_webhook",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Webhook returned HTTP 500")),
    )
    db3 = MagicMock()
    db3.scalars.return_value = [failing_event]
    fail_report = outbox_service.dispatch_pending_outbox_events(db3, dealership_id=1)

    assert fail_report["failed"] == 1
    assert failing_event.status == "failed"
    assert "HTTP 500" in failing_event.last_error


def test_governance_reports_and_outbox_endpoints(monkeypatch) -> None:
    admin = SimpleNamespace(
        id=1,
        name="Admin",
        email="admin@apex.com",
        role="dealership_admin",
        dealership_id=1,
        is_active=True,
    )
    summary_data = {
        "dealership_id": 1,
        "inventory": {"total": 5, "by_status": {"available": 4, "sold": 1}, "total_value": 150000.0},
        "leads": {"total": 3, "by_status": {"new": 2, "won": 1}, "won_deal_value": 35000.0},
        "test_drives": {"total": 2, "by_status": {"booked": 1, "completed": 1}},
        "conversations": {"total": 4, "by_channel": {"whatsapp": 2, "website": 2}, "handoff_queue": 1},
        "observability": {"outbox_by_status": {"delivered": 3}, "notifications_by_status": {"sent": 2}},
    }

    monkeypatch.setattr(
        governance_ep.reporting_service,
        "get_dealership_report_summary",
        lambda db, did: summary_data,
    )
    monkeypatch.setattr(
        governance_ep.outbox_service,
        "list_outbox_events",
        lambda *a, **kw: [],
    )
    monkeypatch.setattr(
        governance_ep.outbox_service,
        "dispatch_pending_outbox_events",
        lambda *a, **kw: {"evaluated": 0, "delivered": 0},
    )

    fastapi_app.dependency_overrides[get_current_user] = lambda: admin
    fastapi_app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        with TestClient(fastapi_app) as client:
            rep = client.get("/api/v1/dealerships/1/reports/summary")
            assert rep.status_code == 200
            assert rep.json()["inventory"]["total"] == 5
            assert rep.json()["leads"]["won_deal_value"] == 35000.0

            ob = client.get("/api/v1/dealerships/1/outbox")
            assert ob.status_code == 200
            assert ob.json() == []

            disp = client.post("/api/v1/dealerships/1/outbox/dispatch?dry_run=true")
            assert disp.status_code == 200
    finally:
        fastapi_app.dependency_overrides.clear()
