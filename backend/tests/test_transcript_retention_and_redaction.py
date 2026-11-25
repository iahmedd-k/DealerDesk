from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.api.v1.endpoints import conversations as conversations_ep
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import app as fastapi_app
from app.services import conversation_service, retention_service

pytestmark = pytest.mark.no_db


def test_scrub_sensitive_pii_on_ingest_and_retention() -> None:
    text = "My card is 4532-0151-2234-5678 and SSN 123-45-6789, email john@example.com or +1 415-555-0199"
    ingest_clean, ingest_changed = conversation_service.scrub_sensitive_pii(
        text, include_contact_pii=False
    )
    assert ingest_changed is True
    assert "[REDACTED_CARD]" in ingest_clean
    assert "[REDACTED_SSN]" in ingest_clean
    assert "john@example.com" in ingest_clean

    aged_clean, aged_changed = conversation_service.scrub_sensitive_pii(
        ingest_clean, include_contact_pii=True
    )
    assert aged_changed is True
    assert "[REDACTED_EMAIL]" in aged_clean
    assert "[REDACTED_PHONE]" in aged_clean


def test_staff_message_redaction_endpoint(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    manager = SimpleNamespace(
        id=2,
        name="Manager Ali",
        email="ali@apex.com",
        role="manager",
        dealership_id=1,
        is_active=True,
    )
    redacted_msg = SimpleNamespace(
        id=15,
        conversation_id=5,
        sender_type="customer",
        sender_id=None,
        content="[REDACTED BY STAFF]",
        channel_metadata={"redacted": True, "redaction_reason": "Sensitive info"},
        created_at=now,
    )

    monkeypatch.setattr(
        conversations_ep.conversation_service,
        "redact_message",
        lambda *a, **kw: redacted_msg,
    )
    monkeypatch.setattr(conversations_ep.audit_service, "log_event", lambda *a, **kw: None)

    fastapi_app.dependency_overrides[get_current_user] = lambda: manager
    fastapi_app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        with TestClient(fastapi_app) as client:
            res = client.post(
                "/api/v1/dealerships/1/conversations/5/messages/15/redact",
                json={"reason": "Sensitive info"},
            )
            assert res.status_code == 200
            assert res.json()["content"] == "[REDACTED BY STAFF]"
            assert res.json()["channel_metadata"]["redacted"] is True
    finally:
        fastapi_app.dependency_overrides.clear()


def test_retention_cleanup_redacts_aged_transcript_messages() -> None:
    aged_msg = SimpleNamespace(
        id=99,
        content="Reach me at buyer@example.com or 415-555-0199",
        channel_metadata={},
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 1
    db.query.return_value.join.return_value.filter.return_value.all.return_value = [aged_msg]

    result = retention_service.cleanup_expired_data(db, dry_run=False)

    assert result["cleaned_counts"]["redacted_transcript_messages"] == 1
    assert result["cleaned_counts"]["closed_conversations"] == 1
    assert "[REDACTED_EMAIL]" in aged_msg.content
    assert "[REDACTED_PHONE]" in aged_msg.content
    assert aged_msg.channel_metadata["pii_redacted"] is True
