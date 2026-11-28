import base64
from types import SimpleNamespace

from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ServiceUnavailableError
from app.db.base import Base
from app.models.channel import Conversation, ConversationMessage
from app.models.gmail import GmailMailboxConnection
from app.models.user import User
from app.models.workspace import Dealership
from app.services import gmail_service

pytestmark = pytest.mark.no_db


def test_refresh_token_is_encrypted_and_bound_to_dealership(monkeypatch) -> None:
    key = base64.urlsafe_b64encode(b"g" * 32).decode("ascii")
    monkeypatch.setattr(
        gmail_service,
        "get_settings",
        lambda: SimpleNamespace(gmail_token_encryption_key=SecretStr(key)),
    )
    encrypted = gmail_service._encrypt_refresh_token("refresh-secret", 14)

    assert "refresh-secret" not in encrypted
    assert (
        gmail_service._decrypt_refresh_token(
            SimpleNamespace(
                encrypted_refresh_token=encrypted,
                dealership_id=14,
            )
        )
        == "refresh-secret"
    )
    with pytest.raises(ServiceUnavailableError):
        gmail_service._decrypt_refresh_token(
            SimpleNamespace(
                encrypted_refresh_token=encrypted,
                dealership_id=15,
            )
        )


def test_gmail_message_parser_reads_headers_and_plain_text() -> None:
    content = base64.urlsafe_b64encode(b"Can I book a test drive?").decode("ascii").rstrip("=")
    parsed = gmail_service._message_details(
        {
            "id": "gmail-message-1",
            "internalDate": "1795700000000",
            "snippet": "Can I book a test drive?",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "Customer <buyer@example.com>"},
                    {"name": "Subject", "value": "Test drive request"},
                    {"name": "Message-ID", "value": "<message-1@example.com>"},
                ],
                "body": {"data": content},
            },
        }
    )

    assert parsed["provider_id"] == "gmail-message-1"
    assert parsed["sender"] == "buyer@example.com"
    assert parsed["subject"] == "Test drive request"
    assert parsed["content"] == "Can I book a test drive?"
    assert parsed["message_id"] == "<message-1@example.com>"


def test_gmail_message_parser_preserves_attachment_metadata() -> None:
    parsed = gmail_service._message_details(
        {
            "id": "gmail-message-1",
            "payload": {
                "headers": [],
                "body": {},
                "parts": [
                    {
                        "filename": "repair estimate.pdf",
                        "mimeType": "application/pdf",
                        "body": {"attachmentId": "attachment_1", "size": "1234"},
                    }
                ],
            },
        }
    )

    assert parsed["attachments"] == [
        {
            "attachment_id": "attachment_1",
            "filename": "repair estimate.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        }
    ]


def test_gmail_attachment_download_is_scoped_to_message_metadata(monkeypatch) -> None:
    message = SimpleNamespace(
        external_message_id="provider-message-1",
        channel_metadata={
            "attachments": [
                {
                    "attachment_id": "attachment_1",
                    "filename": "estimate.pdf",
                    "mime_type": "application/pdf",
                    "size": 4,
                }
            ]
        },
    )
    db = SimpleNamespace(
        query=lambda _model: SimpleNamespace(
            join=lambda *_args: SimpleNamespace(
                filter=lambda *_args: SimpleNamespace(first=lambda: message)
            )
        )
    )
    connection = SimpleNamespace()
    monkeypatch.setattr(gmail_service, "_get_connection", lambda *_args: connection)
    monkeypatch.setattr(gmail_service, "_refresh_access_token", lambda _connection: "token")
    monkeypatch.setattr(
        gmail_service,
        "_gmail_request",
        lambda *_args, **_kwargs: {
            "data": base64.urlsafe_b64encode(b"\x00pdf").decode("ascii").rstrip("=")
        },
    )

    content, mime_type, filename = gmail_service.download_attachment(
        db, 1, 23, "attachment_1"
    )

    assert content == b"\x00pdf"
    assert mime_type == "application/pdf"
    assert filename == "estimate.pdf"
    with pytest.raises(NotFoundError):
        gmail_service.download_attachment(db, 1, 23, "attachment_other")


def test_sync_imports_initial_threads_then_only_new_gmail_messages(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Dealership.__table__,
            User.__table__,
            Conversation.__table__,
            ConversationMessage.__table__,
            GmailMailboxConnection.__table__,
        ],
    )
    message1 = _gmail_message("message-1", "1795700000000", "Initial question")
    message2 = _gmail_message("message-2", "1795700100000", "Follow-up question")
    thread_fetches = 0

    def fake_gmail_request(access_token, method, resource, *, params=None, json_body=None):
        nonlocal thread_fetches
        if resource == "profile":
            return {"historyId": "history-1"}
        if resource == "threads":
            return {"threads": [{"id": "thread-1"}]}
        if resource == "threads/thread-1":
            thread_fetches += 1
            return {"messages": [message1] if thread_fetches == 1 else [message1, message2]}
        if resource == "history" and params["startHistoryId"] == "history-1":
            return {
                "history": [
                    {
                        "messagesAdded": [
                            {"message": {"id": "message-2", "threadId": "thread-1"}}
                        ]
                    }
                ],
                "historyId": "history-2",
            }
        if resource == "history":
            return {"history": [], "historyId": "history-2"}
        raise AssertionError(f"Unexpected Gmail API resource: {resource}")

    monkeypatch.setattr(gmail_service, "_refresh_access_token", lambda connection: "access")
    monkeypatch.setattr(gmail_service, "_gmail_request", fake_gmail_request)
    with Session(engine) as db:
        dealership = Dealership(name="Apex Motors", email="sales@apex.example")
        db.add(dealership)
        db.flush()
        db.add(
            GmailMailboxConnection(
                dealership_id=dealership.id,
                gmail_address="sales@apex.example",
                encrypted_refresh_token="encrypted",
            )
        )
        db.commit()

        assert gmail_service.sync_mailbox(db, dealership.id) == {
            "threads": 1,
            "messages": 1,
        }
        assert gmail_service.sync_mailbox(db, dealership.id) == {
            "threads": 0,
            "messages": 1,
        }
        assert gmail_service.sync_mailbox(db, dealership.id) == {
            "threads": 0,
            "messages": 0,
        }
        messages = db.query(ConversationMessage).all()
        assert len(messages) == 2
        assert {message.external_message_id for message in messages} == {
            "message-1",
            "message-2",
        }
    engine.dispose()


def _gmail_message(message_id: str, internal_date: str, content: str) -> dict:
    encoded = base64.urlsafe_b64encode(content.encode("utf-8")).decode("ascii").rstrip("=")
    return {
        "id": message_id,
        "internalDate": internal_date,
        "snippet": content,
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "Customer <buyer@example.com>"},
                {"name": "Subject", "value": "Test drive request"},
                {"name": "Message-ID", "value": f"<{message_id}@example.com>"},
            ],
            "body": {"data": encoded},
        },
    }
