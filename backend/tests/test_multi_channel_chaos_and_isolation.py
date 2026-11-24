from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    llm_circuit_breaker,
    voice_circuit_breaker,
    whatsapp_circuit_breaker,
)
from app.core.roles import CUSTOMER_ROLE, DEALERDESK_ADMIN_ROLE, MANAGER_ROLE
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.channel import Conversation, ConversationMessage, TestDriveSlotHold
from app.models.user import User
from app.models.workspace import Brand, CustomerLead, Dealership, TestDriveBooking, TestDriveSlot, Vehicle
from app.orchestration import orchestrator
from app.schemas.channel import ChannelEvent, ChannelType
from app.services import conversation_service

# Disable pytest class collection on SQLAlchemy models
TestDriveSlotHold.__test__ = False
TestDriveSlot.__test__ = False
TestDriveBooking.__test__ = False

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
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_dealership_and_inventory(db):
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

    now = datetime.now(timezone.utc)
    slot = TestDriveSlot(
        dealership_id=dealership.id,
        vehicle_id=vehicle.id,
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, minutes=30),
        capacity=2,
        booked_count=0,
        is_active=True,
    )
    db.add(slot)
    db.commit()

    return dealership, vehicle, slot


# =====================================================================
# 1. CROSS-CHANNEL IDENTITY LINKING & ISOLATION (Phase 8)
# =====================================================================

def test_cross_channel_customer_identity_linking(db):
    """
    Verifies that when a customer with a phone number interacts across channels
    (Website verification -> WhatsApp interaction), the system automatically links
    them to their verified Customer User account.
    """
    dealership, vehicle, slot = _seed_dealership_and_inventory(db)
    phone = "+15550198888"
    phone_digits = "15550198888"
    synthetic_email = f"phone_{phone_digits}@customer.dealerdesk.local"

    # 1. Verified customer account created (e.g. from test-drive OTP verification)
    user = User(
        dealership_id=dealership.id,
        name="Chloe Customer",
        email=synthetic_email,
        password="hashedpassword",
        role=CUSTOMER_ROLE,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    # 2. Inbound event arrives via WhatsApp with sender phone number
    wa_event = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WHATSAPP,
        channel_user_id=phone,
        message="What cars are available?",
    )

    result = orchestrator.dispatch_event(db, wa_event)

    # 3. Customer identity should be resolved and linked to user.id
    assert result.customer_id == user.id
    assert result.target_agent == "sales_agent"

    # Verify conversation record in DB has customer_id linked
    conv = db.query(Conversation).filter(Conversation.id == result.conversation_id).first()
    assert conv is not None
    assert conv.customer_id == user.id


def test_channel_session_isolation_and_privacy(db):
    """
    Ensures that conversation turns and sessions across different channels/customers
    remain strictly segregated without any data or message leakage.
    """
    dealership, vehicle, slot = _seed_dealership_and_inventory(db)

    # Customer A on Website
    event_a = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WEBSITE,
        channel_user_id="web_session_alpha",
        message="I am looking for a family SUV",
    )
    result_a = orchestrator.dispatch_event(db, event_a)

    # Customer B on WhatsApp
    event_b = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WHATSAPP,
        channel_user_id="+15550199999",
        message="Do you have sports sedans?",
    )
    result_b = orchestrator.dispatch_event(db, event_b)

    # Verify completely distinct conversation IDs
    assert result_a.conversation_id != result_b.conversation_id

    # Messages of A are only in A's history
    history_a = conversation_service.get_conversation_history(db, result_a.conversation_id)
    history_b = conversation_service.get_conversation_history(db, result_b.conversation_id)

    assert any("family SUV" in m.content for m in history_a)
    assert not any("family SUV" in m.content for m in history_b)

    assert any("sports sedans" in m.content for m in history_b)
    assert not any("sports sedans" in m.content for m in history_a)


# =====================================================================
# 2. FAULT ISOLATION & CHAOS SCENARIOS (Phase 9)
# =====================================================================

def test_llm_outage_circuit_breaker_and_grounded_fallback(db):
    """
    Simulates an external LLM provider outage.
    The circuit breaker catches the failure, trips, and invokes deterministic
    grounded fallback synthesis without crashing or returning an error to the customer.
    Core CRM services remain 100% operational.
    """
    dealership, vehicle, slot = _seed_dealership_and_inventory(db)

    event = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WEBSITE,
        channel_user_id="web_session_resilience",
        message="What vehicles do you have in stock?",
    )

    # Patch LLM generate_completion to simulate provider timeout/outage
    with patch("app.services.llm_service.generate_completion", side_effect=RuntimeError("LLM API Gateway Timeout")):
        result = orchestrator.dispatch_event(db, event)

    # Result still succeeds using grounded fallback
    assert result.response_text is not None
    assert len(result.response_text) > 0
    assert "Apex Solaris" in result.response_text
    assert result.target_agent == "sales_agent"

    # Core inventory database query still returns valid vehicles
    vehicles = db.query(Vehicle).filter(Vehicle.dealership_id == dealership.id).all()
    assert len(vehicles) == 1
    assert vehicles[0].model == "Solaris"


def test_whatsapp_webhook_deduplication(client, db):
    """
    Tests that duplicate webhook payloads from Meta WhatsApp Cloud API retries
    are safely de-duplicated, preventing duplicate conversation turns or bookings.
    """
    dealership, vehicle, slot = _seed_dealership_and_inventory(db)

    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15550199", "phone_number_id": "123456"},
                            "messages": [
                                {
                                    "from": "+15550198888",
                                    "id": "wamid.HBgLMjE2OTkwMjYwNzAVAgASGBQzQTkyREFDN0VBMzA3RjQ0MDk1RAA=",
                                    "timestamp": "1700000000",
                                    "text": {"body": "Hello, show me available cars"},
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

    # 1. First webhook delivery
    res1 = client.post(
        f"/api/v1/dealerships/{dealership.id}/channels/whatsapp/webhook",
        json=webhook_payload,
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "ok"
    assert "outbound" in data1

    # Count conversation messages
    msg_count_1 = db.query(ConversationMessage).count()

    # 2. Second delivery of identical webhook retry from Meta
    res2 = client.post(
        f"/api/v1/dealerships/{dealership.id}/channels/whatsapp/webhook",
        json=webhook_payload,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "ok"
    assert data2.get("message") == "Duplicate event ignored"

    # Message count in DB remains unchanged (no duplicate turns logged)
    msg_count_2 = db.query(ConversationMessage).count()
    assert msg_count_1 == msg_count_2


def test_voice_channel_provider_failure_isolation(client, db):
    """
    Verifies that if an error occurs within voice processing,
    the voice endpoint returns safe fallback TwiML and does not bring down
    other channels or core CRM operations.
    """
    dealership, vehicle, slot = _seed_dealership_and_inventory(db)

    # Patch voice_circuit_breaker.call to raise error
    with patch("app.core.circuit_breaker.voice_circuit_breaker.call", side_effect=RuntimeError("Telephony Timeout")):
        res = client.post(
            f"/api/v1/dealerships/{dealership.id}/channels/voice/webhook",
            data={"SpeechResult": "I want to schedule a test drive", "From": "+15550197777"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

    # Returns graceful fallback TwiML
    assert res.status_code == 200
    assert "application/xml" in res.headers["content-type"]
    assert "Thank you for calling" in res.text
    assert "<Hangup/>" in res.text

    # Website channel still works completely normally
    web_res = client.post(
        f"/api/v1/dealerships/{dealership.id}/channels/website/message",
        json={"session_id": "web_isolated_test", "message": "Show inventory"},
    )
    assert web_res.status_code == 200
    assert web_res.json()["channel"] == "website"
    assert len(web_res.json()["text"]) > 0
