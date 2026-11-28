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

    def fake_update_status(
        db,
        did,
        cid,
        *,
        status,
        staff_user,
        assigned_to_user_id=None,
        assignment_provided=False,
        handoff_reason=None,
    ):
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

            email_filter_res = client.get(
                "/api/v1/dealerships/1/conversations?channel=email&page=1&page_size=25"
            )
            assert email_filter_res.status_code == 200

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


def test_email_staff_reply_is_sent_through_gmail(monkeypatch) -> None:
    from app.services import conversation_service, gmail_service

    staff = SimpleNamespace(id=2, name="Manager Ali", email="ali@apex.com")
    conversation = SimpleNamespace(
        id=5,
        channel="email",
        external_thread_id="gmail-thread-7",
        dealership_id=1,
    )
    sent = {}
    saved = SimpleNamespace(id=11, sender_type="staff")

    monkeypatch.setattr(
        conversation_service,
        "get_conversation_for_dealership",
        lambda db, dealership_id, conversation_id: conversation,
    )

    def fake_send_reply(db, conv, user, content):
        sent["reply"] = (conv.external_thread_id, user.id, content)
        return {
            "provider_message_id": "gmail-message-8",
            "rfc822_message_id": "<reply@example.com>",
            "references": "<message-1@example.com>",
        }

    def fake_append_message(
        db,
        conversation_id,
        sender_type,
        content,
        sender_id=None,
        channel_metadata=None,
        external_message_id=None,
    ):
        sent["saved"] = {
            "sender_type": sender_type,
            "content": content,
            "sender_id": sender_id,
            "channel_metadata": channel_metadata,
            "external_message_id": external_message_id,
        }
        return saved

    monkeypatch.setattr(gmail_service, "send_reply", fake_send_reply)
    monkeypatch.setattr(conversation_service, "append_message", fake_append_message)

    result = conversation_service.add_staff_reply(
        object(),
        dealership_id=1,
        conversation_id=5,
        staff_user=staff,
        content="  I can help with that.  ",
    )

    assert result is saved
    assert sent["reply"] == ("gmail-thread-7", 2, "I can help with that.")
    assert sent["saved"]["external_message_id"] == "gmail-message-8"
    assert sent["saved"]["channel_metadata"]["rfc822_message_id"] == "<reply@example.com>"


def test_whatsapp_staff_reply_is_sent_through_twilio(monkeypatch) -> None:
    from app.channels.whatsapp import service as whatsapp_service
    from app.core import config
    from app.services import conversation_service

    staff = SimpleNamespace(id=2, name="Manager Ali", email="ali@apex.com")
    conversation = SimpleNamespace(
        id=5,
        channel="whatsapp",
        channel_user_id="+14155550100",
        dealership_id=1,
    )
    dealership = SimpleNamespace(is_active=True, whatsapp_number="+14155550123")
    sent = {}
    saved = SimpleNamespace(id=11, sender_type="staff")
    db = MagicMock()
    db.get.return_value = dealership
    db.scalar.return_value = None

    monkeypatch.setattr(
        conversation_service,
        "get_conversation_for_dealership",
        lambda _db, _dealership_id, _conversation_id: conversation,
    )
    monkeypatch.setattr(
        whatsapp_service,
        "get_whatsapp_service",
        lambda: SimpleNamespace(
            send_message=lambda **kwargs: sent.update(kwargs)
            or {"sid": "SM123", "status": "queued"}
        ),
    )
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(twilio_status_callback_url="https://crm.example/status"),
    )
    monkeypatch.setattr(
        conversation_service,
        "append_message",
        lambda _db, conversation_id, sender_type, content, sender_id=None,
        channel_metadata=None, external_message_id=None: sent.update(
            {
                "saved_conversation_id": conversation_id,
                "sender_type": sender_type,
                "content": content,
                "sender_id": sender_id,
                "metadata": channel_metadata,
                "external_message_id": external_message_id,
            }
        )
        or saved,
    )

    result = conversation_service.add_staff_reply(
        db,
        dealership_id=1,
        conversation_id=5,
        staff_user=staff,
        content="  I can help with that.  ",
    )

    assert result is saved
    assert sent["to"] == "+14155550100"
    assert sent["body"] == "I can help with that."
    assert sent["from_override"] == "whatsapp:+14155550123"
    assert sent["status_callback"] == "https://crm.example/status"
    assert sent["external_message_id"] == "SM123"
    assert sent["metadata"]["provider_status"] == "queued"


def test_staff_reply_rejects_unsupported_channel(monkeypatch) -> None:
    from app.core.errors import UnprocessableEntityError
    from app.services import conversation_service

    monkeypatch.setattr(
        conversation_service,
        "get_conversation_for_dealership",
        lambda *_args: SimpleNamespace(channel="voice"),
    )
    with pytest.raises(UnprocessableEntityError, match="Replies are not supported"):
        conversation_service.add_staff_reply(
            MagicMock(),
            dealership_id=1,
            conversation_id=5,
            staff_user=SimpleNamespace(id=2, name="Manager Ali", email="ali@apex.com"),
            content="Follow-up",
        )
