from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.api.v1.endpoints import conversations as conversations_ep
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import app as fastapi_app

pytestmark = pytest.mark.no_db


def test_conversation_inbox_list_detail_handoff_and_reply(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    staff = SimpleNamespace(
        id=2,
        name="Manager Ali",
        email="ali@apex.com",
        role="manager",
        dealership_id=1,
        is_active=True,
    )
    msg1 = SimpleNamespace(
        id=10,
        conversation_id=5,
        sender_type="customer",
        sender_id=None,
        content="Hi, is the 2025 Camry available?",
        channel_metadata={},
        created_at=now,
    )
    conv = SimpleNamespace(
        id=5,
        dealership_id=1,
        channel="whatsapp",
        channel_user_id="whatsapp:+14155550100",
        customer_id=None,
        status="active",
        channel_metadata={},
        messages=[msg1],
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr(
        conversations_ep.conversation_service,
        "list_conversations",
        lambda *a, **kw: [conv],
    )
    monkeypatch.setattr(
        conversations_ep.conversation_service,
        "count_conversations",
        lambda *a, **kw: 1,
    )
    monkeypatch.setattr(
        conversations_ep.conversation_service,
        "get_conversation_for_dealership",
        lambda db, did, cid: conv,
    )

    def fake_update_status(db, did, cid, *, status, staff_user, assigned_to_user_id=None, handoff_reason=None):
        conv.status = status
        conv.channel_metadata = {
            "assigned_to_user_id": assigned_to_user_id,
            "assigned_to_name": "Manager Ali",
            "handoff_reason": handoff_reason,
        }
        return conv

    monkeypatch.setattr(
        conversations_ep.conversation_service,
        "update_conversation_status",
        fake_update_status,
    )
    monkeypatch.setattr(
        conversations_ep.audit_service,
        "log_event",
        lambda *a, **kw: None,
    )

    def fake_add_reply(db, did, cid, user, content):
        return SimpleNamespace(
            id=11,
            conversation_id=cid,
            sender_type="staff",
            sender_id=user.id,
            content=content,
            channel_metadata={"staff_name": user.name},
            created_at=now,
        )

    monkeypatch.setattr(
        conversations_ep.conversation_service,
        "add_staff_reply",
        fake_add_reply,
    )

    fastapi_app.dependency_overrides[get_current_user] = lambda: staff
    fastapi_app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        with TestClient(fastapi_app) as client:
            list_res = client.get(
                "/api/v1/dealerships/1/conversations?channel=whatsapp&page=1&page_size=25"
            )
            assert list_res.status_code == 200
            assert list_res.headers["X-Total-Count"] == "1"
            assert list_res.json()[0]["channel"] == "whatsapp"
            assert list_res.json()[0]["message_count"] == 1

            detail_res = client.get("/api/v1/dealerships/1/conversations/5")
            assert detail_res.status_code == 200
            assert len(detail_res.json()["messages"]) == 1

            handoff_res = client.patch(
                "/api/v1/dealerships/1/conversations/5/status",
                json={
                    "status": "handed_off",
                    "assigned_to_user_id": 2,
                    "handoff_reason": "Customer requested financing callback",
                },
            )
            assert handoff_res.status_code == 200
            assert handoff_res.json()["status"] == "handed_off"
            assert handoff_res.json()["handoff_reason"] == "Customer requested financing callback"

            reply_res = client.post(
                "/api/v1/dealerships/1/conversations/5/messages",
                json={"content": "Calling the customer shortly."},
            )
            assert reply_res.status_code == 201
            assert reply_res.json()["sender_type"] == "staff"
    finally:
        fastapi_app.dependency_overrides.clear()
