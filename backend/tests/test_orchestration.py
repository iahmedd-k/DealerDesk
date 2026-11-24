from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.roles import CUSTOMER_ROLE, DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.channel import Conversation, ConversationMessage, TestDriveSlotHold
from app.models.user import User
from app.models.workspace import Brand, Dealership, Vehicle
from app.orchestration import orchestrator
from app.schemas.channel import ChannelEvent, ChannelType

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


def _seed_orchestration_data(db):
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

    staff_user = User(
        dealership_id=dealership.id,
        name="Manager Marcus",
        email="marcus@apexmotors.com",
        password="hashedpassword",
        role=MANAGER_ROLE,
        is_active=True,
    )
    customer_user = User(
        dealership_id=dealership.id,
        name="Customer Chloe",
        email="chloe@example.com",
        password="hashedpassword",
        role=CUSTOMER_ROLE,
        is_active=True,
    )
    db.add_all([staff_user, customer_user])
    db.commit()

    return dealership, vehicle, staff_user, customer_user


# =====================================================================
# 1. AGENT ROUTING TESTS
# =====================================================================

def test_orchestrator_routes_customer_channels_to_sales_agent(db_session):
    dealership, vehicle, _, customer_user = _seed_orchestration_data(db_session)

    # 1. Web event
    web_event = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WEBSITE,
        channel_user_id="web-sess-100",
        message="What sedans do you have in stock?",
    )
    web_result = orchestrator.dispatch_event(db_session, web_event, current_user=customer_user)
    assert web_result.target_agent == "sales_agent"
    assert web_result.channel == "website"
    assert web_result.conversation_id is not None
    assert "outbound_payload" in dir(web_result)
    assert web_result.outbound_payload["channel"] == "website"

    # 2. WhatsApp event
    wa_event = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WHATSAPP,
        channel_user_id="+15552345678",
        message="Hi, can I see your inventory?",
    )
    wa_result = orchestrator.dispatch_event(db_session, wa_event)
    assert wa_result.target_agent == "sales_agent"
    assert wa_result.channel == "whatsapp"
    assert wa_result.outbound_payload["messaging_product"] == "whatsapp"

    # 3. Voice event
    voice_event = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.VOICE,
        channel_user_id="+15559876543",
        message="I'd like to ask about car prices.",
    )
    voice_result = orchestrator.dispatch_event(db_session, voice_event)
    assert voice_result.target_agent == "sales_agent"
    assert voice_result.channel == "voice"
    assert "<Response>" in voice_result.outbound_payload["twiml"]


def test_orchestrator_routes_staff_dashboard_to_crm_agent(db_session):
    dealership, _, staff_user, _ = _seed_orchestration_data(db_session)

    staff_event = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WEBSITE,
        channel_user_id="staff-session-admin",
        message="What are our showroom hours today?",
        metadata={"origin": "staff_dashboard"},
    )

    result = orchestrator.dispatch_event(db_session, staff_event, current_user=staff_user)
    assert result.target_agent == "crm_agent"
    assert result.dealership_id == dealership.id
    assert result.conversation_id is not None


# =====================================================================
# 2. CHANNEL SESSION ISOLATION & PERSISTENCE
# =====================================================================

def test_channel_session_isolation(db_session):
    dealership, _, _, _ = _seed_orchestration_data(db_session)

    # Web session
    event1 = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WEBSITE,
        channel_user_id="user_alpha",
        message="Web message turn 1",
    )
    res1 = orchestrator.dispatch_event(db_session, event1)

    # WhatsApp session with same user identifier
    event2 = ChannelEvent(
        dealership_id=dealership.id,
        channel=ChannelType.WHATSAPP,
        channel_user_id="user_alpha",
        message="WhatsApp message turn 1",
    )
    res2 = orchestrator.dispatch_event(db_session, event2)

    # Sessions must be isolated by channel
    assert res1.conversation_id != res2.conversation_id

    conv1 = db_session.query(Conversation).filter(Conversation.id == res1.conversation_id).first()
    conv2 = db_session.query(Conversation).filter(Conversation.id == res2.conversation_id).first()
    assert conv1.channel == "website"
    assert conv2.channel == "whatsapp"


# =====================================================================
# 3. UNIFIED ORCHESTRATION API ENDPOINT
# =====================================================================

def test_orchestration_api_endpoint(client, db_session):
    dealership, _, _, _ = _seed_orchestration_data(db_session)

    payload = {
        "dealership_id": dealership.id,
        "channel": "website",
        "channel_user_id": "api_client_orch_1",
        "message": "Do you have any sedans?",
        "metadata": {"brand_id": 1},
    }

    res = client.post(
        f"/api/v1/dealerships/{dealership.id}/orchestrate",
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["target_agent"] == "sales_agent"
    assert data["channel"] == "website"
    assert "conversation_id" in data
    assert "outbound" in data
