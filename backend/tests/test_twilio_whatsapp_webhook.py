from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator
from pydantic import SecretStr

from app.channels.whatsapp import router as whatsapp_router
from app.main import app
from app.channels.whatsapp.schemas import TwilioInboundMessage, WhatsAppOutboundMessage
from app.channels.whatsapp.service import TwilioWhatsAppService, get_whatsapp_service
from app.db.session import get_db

pytestmark = pytest.mark.no_db

client = TestClient(app)


def test_whatsapp_webhook_get_status():
    """Verify GET status endpoint on WhatsApp webhook."""
    response = client.get("/api/v1/channels/whatsapp/webhook")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["channel"] == "whatsapp"
    assert data["provider"] == "twilio"


def test_whatsapp_webhook_inbound_post_twiml_response(monkeypatch):
    """Verify Twilio POST webhook receives form fields and returns valid TwiML XML."""
    token = "test-twilio-token"
    monkeypatch.setattr(
        whatsapp_router,
        "get_settings",
        lambda: SimpleNamespace(
            twilio_auth_token=SecretStr(token),
            twilio_webhook_base_url=None,
        ),
    )
    monkeypatch.setattr(
        whatsapp_router,
        "_dealership_for_number",
        lambda _db, _number: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(
        whatsapp_router.orchestrator,
        "dispatch_event",
        lambda _db, _event: SimpleNamespace(
            response_text="Hello! Welcome to our dealership."
        ),
    )
    db = MagicMock()
    db.scalar.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    form_data = {
        "From": "whatsapp:+14155551234",
        "To": "whatsapp:+14155550123",
        "Body": "Hello! I want to check car availability.",
        "ProfileName": "Ahmed",
        "MessageSid": "SM9876543210abcdef",
        "WaId": "14155551234",
    }
    signature = RequestValidator(token).compute_signature(
        "http://testserver/api/v1/channels/whatsapp/webhook",
        form_data,
    )
    try:
        response = client.post(
            "/api/v1/channels/whatsapp/webhook",
            data=form_data,
            headers={"X-Twilio-Signature": signature},
        )
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        xml_content = response.text
        assert "<Response>" in xml_content
        assert "<Message>Hello! Welcome to our dealership.</Message>" in xml_content
        assert "</Response>" in xml_content
    finally:
        app.dependency_overrides.clear()


def test_whatsapp_webhook_root_alias_post(monkeypatch):
    """Verify direct alias route /channels/whatsapp/webhook also works."""
    async def accept_signature(_request):
        return {
            "From": "whatsapp:+19876543210",
            "To": "whatsapp:+14155550123",
            "Body": "Testing direct route",
            "MessageSid": "SM9876543210abcdef2",
        }

    monkeypatch.setattr(whatsapp_router, "_validated_twilio_form", accept_signature)
    monkeypatch.setattr(
        whatsapp_router,
        "_dealership_for_number",
        lambda _db, _number: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(
        whatsapp_router.orchestrator,
        "dispatch_event",
        lambda _db, _event: SimpleNamespace(
            response_text="Hello! Welcome to our dealership."
        ),
    )
    db = MagicMock()
    db.scalar.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    form_data = {
        "From": "whatsapp:+19876543210",
        "To": "whatsapp:+14155550123",
        "Body": "Testing direct route",
        "MessageSid": "SM9876543210abcdef2",
    }
    try:
        response = client.post("/channels/whatsapp/webhook", data=form_data)
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        assert "Hello! Welcome to our dealership." in response.text
    finally:
        app.dependency_overrides.clear()


def test_whatsapp_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(
        whatsapp_router,
        "get_settings",
        lambda: SimpleNamespace(twilio_auth_token=None),
    )
    response = client.post(
        "/api/v1/channels/whatsapp/webhook",
        data={
            "From": "whatsapp:+19876543210",
            "To": "whatsapp:+14155550123",
            "Body": "Hello",
            "MessageSid": "SM9876543210abcdef3",
        },
    )
    assert response.status_code == 503


def test_whatsapp_webhook_rejects_invalid_signature(monkeypatch):
    token = "test-twilio-token"
    monkeypatch.setattr(
        whatsapp_router,
        "get_settings",
        lambda: SimpleNamespace(
            twilio_auth_token=SecretStr(token),
            twilio_webhook_base_url=None,
        ),
    )
    response = client.post(
        "/api/v1/channels/whatsapp/webhook",
        data={
            "From": "whatsapp:+19876543210",
            "To": "whatsapp:+14155550123",
            "Body": "Hello",
            "MessageSid": "SM9876543210abcdef4",
        },
        headers={"X-Twilio-Signature": "invalid"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("current", "incoming", "expected"),
    [
        (None, "queued", True),
        ("queued", "sent", True),
        ("sent", "delivered", True),
        ("delivered", "read", True),
        ("delivered", "sent", False),
        ("read", "failed", False),
        ("failed", "delivered", False),
        ("queued", "unknown", False),
    ],
)
def test_twilio_delivery_status_only_advances(current, incoming, expected):
    assert whatsapp_router._is_delivery_status_advance(current, incoming) is expected


def test_twilio_inbound_schema():
    """Verify TwilioInboundMessage parses Twilio form data aliases."""
    payload = {
        "From": "whatsapp:+1234567890",
        "Body": "Inquiry about sedan",
        "To": "whatsapp:+19062561491",
        "MessageSid": "SM123",
        "ProfileName": "Customer Name",
        "NumMedia": "0",
    }
    msg = TwilioInboundMessage.model_validate(payload)
    assert msg.from_number == "whatsapp:+1234567890"
    assert msg.body == "Inquiry about sedan"
    assert msg.profile_name == "Customer Name"
    assert msg.to_number == "whatsapp:+19062561491"
    assert msg.num_media == 0


def test_twilio_whatsapp_service_twiml_generation():
    """Verify TwilioWhatsAppService generates valid TwiML MessagingResponse."""
    service = get_whatsapp_service()
    twiml_output = service.create_twiml_reply("Welcome to our test drive booking!")
    assert "<Response>" in twiml_output
    assert "<Message>Welcome to our test drive booking!</Message>" in twiml_output
