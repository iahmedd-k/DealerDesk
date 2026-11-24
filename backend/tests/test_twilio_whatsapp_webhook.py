import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.channels.whatsapp.schemas import TwilioInboundMessage, WhatsAppOutboundMessage
from app.channels.whatsapp.service import TwilioWhatsAppService, get_whatsapp_service

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


def test_whatsapp_webhook_inbound_post_twiml_response():
    """Verify Twilio POST webhook receives form fields and returns valid TwiML XML."""
    form_data = {
        "From": "whatsapp:+14155551234",
        "Body": "Hello! I want to check car availability.",
        "ProfileName": "Ahmed",
        "MessageSid": "SM9876543210abcdef",
        "WaId": "14155551234",
    }
    response = client.post("/api/v1/channels/whatsapp/webhook", data=form_data)
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    xml_content = response.text
    assert "<Response>" in xml_content
    assert "<Message>Hello! Welcome to our dealership.</Message>" in xml_content
    assert "</Response>" in xml_content


def test_whatsapp_webhook_root_alias_post():
    """Verify direct alias route /channels/whatsapp/webhook also works."""
    form_data = {
        "From": "whatsapp:+19876543210",
        "Body": "Testing direct route",
    }
    response = client.post("/channels/whatsapp/webhook", data=form_data)
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "Hello! Welcome to our dealership." in response.text


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
