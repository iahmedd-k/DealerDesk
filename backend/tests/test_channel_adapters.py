import hmac
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters import get_channel_adapter
from app.adapters.voice_adapter import VoiceAdapter
from app.adapters.website_adapter import WebsiteAdapter
from app.adapters.whatsapp_adapter import WhatsAppAdapter
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.channel import Conversation, ConversationMessage, TestDriveSlotHold
from app.models.workspace import Brand, Dealership, Vehicle
from app.schemas.channel import ChannelType
from app.schemas.sales_agent import SalesAgentChatResponse

TestDriveSlotHold.__test__ = False
pytestmark = pytest.mark.no_db

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def setup_sqlite():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_dealership(db):
    dealership = Dealership(
        name="Apex Motors",
        email="info@apexmotors.com",
        phone="555-0199",
        address="100 Motor Way",
        is_active=True,
    )
    db.add(dealership)
    db.commit()

    brand = Brand(dealership_id=dealership.id, name="Apex", is_active=True, is_deleted=False)
    db.add(brand)
    db.commit()

    vehicle = Vehicle(
        dealership_id=dealership.id,
        brand_id=brand.id,
        make="Apex",
        model="Solaris",
        model_year=2024,
        price=Decimal("28000.00"),
        stock_number="SOL-001",
        is_available=True,
        test_drive_enabled=True,
    )
    db.add(vehicle)
    db.commit()
    return dealership, vehicle


# =====================================================================
# 1. WEBSITE ADAPTER TESTS
# =====================================================================

def test_website_adapter_inbound_and_outbound():
    adapter = WebsiteAdapter()
    assert adapter.channel_type == ChannelType.WEBSITE

    # Parse inbound
    event = adapter.parse_inbound(
        dealership_id=1,
        payload={"message": "Looking for a sedan", "channel_user_id": "web-session-123"},
        headers={"user-agent": "Mozilla/5.0"},
    )
    assert event.dealership_id == 1
    assert event.channel == ChannelType.WEBSITE
    assert event.channel_user_id == "web-session-123"
    assert event.message == "Looking for a sedan"

    # Format outbound
    dummy_response = SalesAgentChatResponse(
        response="We have the Apex Solaris available for $28,000.",
        dealership_id=1,
        dealership_name="Apex Motors",
        conversation_id=42,
        intent="inventory_inquiry",
        matched_vehicles=[{"id": 1, "make": "Apex", "model": "Solaris", "price": 28000}],
        suggested_actions=["Book a test drive", "Ask about financing"],
    )
    outbound = adapter.format_outbound(dummy_response, recipient="web-session-123")
    assert outbound["channel"] == "website"
    assert outbound["conversation_id"] == 42
    assert len(outbound["cards"]) == 1
    assert len(outbound["actions"]) == 2


# =====================================================================
# 2. WHATSAPP ADAPTER TESTS
# =====================================================================

def test_whatsapp_adapter_signature_verification():
    adapter = WhatsAppAdapter()
    secret = "my_app_secret_123"
    body = b'{"object":"whatsapp_business_account"}'

    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert adapter.verify_signature(body, signature, secret) is True
    assert adapter.verify_signature(body, "sha256=invalid_signature", secret) is False


def test_whatsapp_adapter_inbound_meta_parsing_and_deduplication():
    adapter = WhatsAppAdapter()

    meta_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15550234567", "phone_number_id": "100234567"},
                            "contacts": [{"profile": {"name": "Jordan"}, "wa_id": "15551234567"}],
                            "messages": [
                                {
                                    "from": "15551234567",
                                    "id": "wamid.HBgLMTU1NTEyMzQ1NjcVAgASGBQzQTkyREIzQUU3NzQ1RTQxOTY5NwA=",
                                    "timestamp": "1710000000",
                                    "text": {"body": "Hi, do you have electric SUVs?"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    # First delivery
    event = adapter.parse_inbound(dealership_id=1, payload=meta_payload)
    assert event.channel == ChannelType.WHATSAPP
    assert event.channel_user_id == "15551234567"
    assert event.message == "Hi, do you have electric SUVs?"
    assert event.metadata.get("is_duplicate") is False

    # Immediate redelivery (webhook retry) -> Must flag as duplicate
    duplicate_event = adapter.parse_inbound(dealership_id=1, payload=meta_payload)
    assert duplicate_event.metadata.get("is_duplicate") is True


def test_whatsapp_adapter_outbound_interactive_buttons():
    adapter = WhatsAppAdapter()
    dummy_response = SalesAgentChatResponse(
        response="We have 2 SUVs in stock.",
        dealership_id=1,
        dealership_name="Apex Motors",
        intent="inventory_inquiry",
        suggested_actions=["Book Test Drive", "Ask Financing"],
    )

    outbound = adapter.format_outbound(dummy_response, recipient="+15551234567")
    assert outbound["messaging_product"] == "whatsapp"
    assert outbound["to"] == "15551234567"
    assert outbound["type"] == "interactive"
    buttons = outbound["interactive"]["action"]["buttons"]
    assert len(buttons) == 2
    assert buttons[0]["reply"]["title"] == "Book Test Drive"


# =====================================================================
# 3. VOICE TELEPHONY ADAPTER TESTS
# =====================================================================

def test_voice_adapter_spoken_sanitization_and_pricing():
    # Markdown removal & price verbalization
    markdown_text = (
        "We have the **Apex Solaris** for **$28,000**! "
        "Key features include: \n- *Lane assist*\n- Touchscreen display."
    )
    spoken = VoiceAdapter.sanitize_for_speech(markdown_text)

    assert "**" not in spoken
    assert "- " not in spoken
    assert "28 thousand dollars" in spoken


def test_voice_adapter_inbound_and_twiml_generation():
    adapter = VoiceAdapter()

    telephony_payload = {
        "CallSid": "CA1234567890abcdef",
        "From": "+15559876543",
        "SpeechResult": "I would like to schedule a test drive tomorrow.",
        "Confidence": "0.94",
        "CallStatus": "in-progress",
    }

    event = adapter.parse_inbound(dealership_id=1, payload=telephony_payload)
    assert event.channel == ChannelType.VOICE
    assert event.channel_user_id == "+15559876543"
    assert event.message == "I would like to schedule a test drive tomorrow."

    dummy_response = SalesAgentChatResponse(
        response="We have test drive slots available at 10 AM.",
        dealership_id=1,
        dealership_name="Apex Motors",
        intent="test_drive_booking",
    )
    outbound = adapter.format_outbound(dummy_response, recipient="+15559876543")
    assert "<Response>" in outbound["twiml"]
    assert "<Say" in outbound["twiml"]
    assert "<Gather" in outbound["twiml"]
    assert "10 AM" in outbound["twiml"]


# =====================================================================
# 4. CHANNEL API ROUTER INTEGRATION TESTS
# =====================================================================

def test_channel_api_endpoints_integration(client, db_session):
    dealership, _ = _seed_dealership(db_session)

    # 1. Website channel endpoint
    web_res = client.post(
        f"/api/v1/dealerships/{dealership.id}/channels/website/message",
        json={"message": "Show me what sedans you have.", "channel_user_id": "web-customer-99"},
    )
    assert web_res.status_code == 200
    assert web_res.json()["channel"] == "website"

    # 2. WhatsApp verification GET challenge
    verify_res = client.get(
        f"/api/v1/dealerships/{dealership.id}/channels/whatsapp/webhook?hub.mode=subscribe&hub.challenge=test_challenge_123&hub.verify_token=dealerdesk_whatsapp_verify_token"
    )
    assert verify_res.status_code == 200
    assert verify_res.text == "test_challenge_123"

    # 3. WhatsApp inbound webhook POST
    wa_res = client.post(
        f"/api/v1/dealerships/{dealership.id}/channels/whatsapp/webhook",
        json={"phone": "+15550001111", "message": "Hi, what are your hours?"},
    )
    assert wa_res.status_code == 200
    assert wa_res.json()["status"] == "ok"
    assert "outbound" in wa_res.json()

    # 4. Voice telephony webhook POST (form-urlencoded)
    voice_res = client.post(
        f"/api/v1/dealerships/{dealership.id}/channels/voice/webhook",
        data={"From": "+15553334444", "SpeechResult": "What cars are in stock?", "CallSid": "CA999"},
    )
    assert voice_res.status_code == 200
    assert "application/xml" in voice_res.headers["content-type"]
    assert "<Response>" in voice_res.text
