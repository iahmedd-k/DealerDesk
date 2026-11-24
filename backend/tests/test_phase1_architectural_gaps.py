from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from app.core.errors import BadRequestError, ConflictError, TooManyRequestsError
from app.db.base import Base
from app.models.channel import Conversation, ConversationMessage, OTPVerification, TestDriveSlotHold
from app.models.workspace import Brand, Dealership, TestDriveSlot, Vehicle
from app.services import conversation_service, otp_service, slot_hold_service

TestDriveSlotHold.__test__ = False
TestDriveSlot.__test__ = False

pytestmark = pytest.mark.no_db

# Use in-memory SQLite database for fast, isolated testing of Phase 1 architecture services
engine = create_engine("sqlite:///:memory:", echo=False)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def setup_sqlite_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_dealership_and_slot(db):
    dealership = Dealership(
        name="Apex Motors",
        email="contact@apexmotors.com",
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
        model="Horizon",
        model_year=2025,
        price=35000,
        stock_number="APX-01",
        is_available=True,
        test_drive_enabled=True,
    )
    db.add(vehicle)
    db.commit()

    now = datetime.now(timezone.utc)
    slot = TestDriveSlot(
        dealership_id=dealership.id,
        vehicle_id=vehicle.id,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, minutes=30),
        capacity=1,
        booked_count=0,
        is_active=True,
    )
    db.add(slot)
    db.commit()
    return dealership, slot


# =====================================================================
# 1. CIRCUIT BREAKER FAULT ISOLATION TESTS
# =====================================================================

def test_circuit_breaker_normal_execution_and_success():
    cb = CircuitBreaker("test_service", failure_threshold=3, recovery_timeout_seconds=5.0)
    assert cb.state == CircuitState.CLOSED

    mock_func = MagicMock(return_value="ok")
    result = cb.call(mock_func, "arg1")

    assert result == "ok"
    assert cb.state == CircuitState.CLOSED
    assert mock_func.call_count == 1


def test_circuit_breaker_trips_to_open_on_threshold():
    cb = CircuitBreaker("failing_service", failure_threshold=2, recovery_timeout_seconds=10.0)

    failing_func = MagicMock(side_effect=RuntimeError("connection refused"))

    with pytest.raises(RuntimeError):
        cb.call(failing_func)
    assert cb.state == CircuitState.CLOSED

    with pytest.raises(RuntimeError):
        cb.call(failing_func)
    assert cb.state == CircuitState.OPEN

    # Subsequent call immediately raises CircuitBreakerOpenError without calling downstream
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        cb.call(failing_func)
    assert "temporarily unavailable" in str(exc_info.value)
    assert failing_func.call_count == 2


# =====================================================================
# 2. SLOT HOLD CONCURRENCY & LEASE TESTS
# =====================================================================

def test_slot_hold_acquisition_and_concurrency(test_db):
    dealership, slot = _seed_dealership_and_slot(test_db)

    # 1. Successfully acquire hold
    hold = slot_hold_service.acquire_slot_hold(
        test_db,
        dealership_id=dealership.id,
        slot_id=slot.id,
        identifier="+1234567890",
        duration_minutes=10,
    )
    assert hold.status == "held"
    assert hold.hold_token.startswith("hold_")
    assert hold.slot_id == slot.id

    # 2. Second hold on same single-capacity slot must fail with ConflictError
    with pytest.raises(ConflictError) as exc_info:
        slot_hold_service.acquire_slot_hold(
            test_db,
            dealership_id=dealership.id,
            slot_id=slot.id,
            identifier="other_customer@example.com",
            duration_minutes=10,
        )
    assert "No remaining capacity" in str(exc_info.value)

    # 3. Releasing hold frees slot
    slot_hold_service.release_slot_hold(test_db, hold.hold_token)
    assert slot_hold_service.get_active_holds_count_for_slot(test_db, slot.id) == 0

    # 4. Now second hold succeeds
    hold2 = slot_hold_service.acquire_slot_hold(
        test_db,
        dealership_id=dealership.id,
        slot_id=slot.id,
        identifier="other_customer@example.com",
    )
    assert hold2.status == "held"

    # 5. Confirming hold updates status
    confirmed = slot_hold_service.confirm_slot_hold(test_db, hold2.hold_token)
    assert confirmed.status == "confirmed"


# =====================================================================
# 3. OTP VERIFICATION ENGINE TESTS
# =====================================================================

def test_otp_flow_generation_verification_and_cooldown(test_db):
    dealership, _ = _seed_dealership_and_slot(test_db)
    identifier = "customer@example.com"

    # 1. Request OTP
    code, expires_at = otp_service.request_otp(
        test_db,
        dealership_id=dealership.id,
        channel="email",
        identifier=identifier,
    )
    assert len(code) == 6
    assert code.isdigit()
    assert expires_at > datetime.now(timezone.utc)

    # 2. Enforces cooldown on immediate re-request
    with pytest.raises(TooManyRequestsError) as exc_info:
        otp_service.request_otp(
            test_db,
            dealership_id=dealership.id,
            channel="email",
            identifier=identifier,
        )
    assert "Please wait" in str(exc_info.value)

    # 3. Invalid code decrements attempts
    with pytest.raises(BadRequestError) as exc_info:
        otp_service.verify_otp(
            test_db,
            dealership_id=dealership.id,
            identifier=identifier,
            code="000000" if code != "000000" else "111111",
        )
    assert "Invalid verification code" in str(exc_info.value)

    # 4. Correct code verifies successfully
    verified = otp_service.verify_otp(
        test_db,
        dealership_id=dealership.id,
        identifier=identifier,
        code=code,
    )
    assert verified is True

    # 5. Single-use: Cannot be verified a second time
    with pytest.raises(BadRequestError) as exc_info:
        otp_service.verify_otp(
            test_db,
            dealership_id=dealership.id,
            identifier=identifier,
            code=code,
        )
    assert "expired or does not exist" in str(exc_info.value)


# =====================================================================
# 4. CONVERSATION & SESSION PERSISTENCE TESTS
# =====================================================================

def test_conversation_persistence_and_multi_turn_history(test_db):
    dealership, _ = _seed_dealership_and_slot(test_db)

    # 1. Get or create conversation session
    conv = conversation_service.get_or_create_conversation(
        test_db,
        dealership_id=dealership.id,
        channel="whatsapp",
        channel_user_id="+15550192834",
    )
    assert conv.id is not None
    assert conv.channel == "whatsapp"
    assert conv.status == "active"

    # 2. Idempotent retrieval of active conversation
    conv_same = conversation_service.get_or_create_conversation(
        test_db,
        dealership_id=dealership.id,
        channel="whatsapp",
        channel_user_id="+15550192834",
    )
    assert conv_same.id == conv.id

    # 3. Append messages
    m1 = conversation_service.append_message(
        test_db,
        conversation_id=conv.id,
        sender_type="customer",
        content="Hi, what SUVs do you have in stock?",
    )
    m2 = conversation_service.append_message(
        test_db,
        conversation_id=conv.id,
        sender_type="agent",
        content="We have the 2025 Apex Horizon available for $35,000.",
    )

    # 4. Fetch chronological history
    history = conversation_service.get_conversation_history(test_db, conv.id, limit=5)
    assert len(history) == 2
    assert history[0].content == "Hi, what SUVs do you have in stock?"
    assert history[1].content == "We have the 2025 Apex Horizon available for $35,000."
    assert history[0].sender_type == "customer"
    assert history[1].sender_type == "agent"
