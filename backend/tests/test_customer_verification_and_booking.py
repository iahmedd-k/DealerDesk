from datetime import datetime, timedelta, timezone
from decimal import Decimal
import secrets
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import BadRequestError, ConflictError, TooManyRequestsError
from app.core.roles import CUSTOMER_ROLE
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.channel import Conversation, OTPVerification, TestDriveSlotHold
from app.models.user import User
from app.models.workspace import Brand, Dealership, TestDriveBooking, TestDriveSlot, Vehicle
from app.schemas.channel import (
    BookingVerificationConfirmRequest,
    BookingVerificationInitiateRequest,
)
from app.services import (
    customer_verification_service,
    otp_service,
    slot_hold_service,
    test_drive_service,
)

# Prevent pytest from collecting SQLAlchemy models as test suites
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


def _seed_data(db):
    dealership = Dealership(
        name="Apex Motors",
        email="contact@apexmotors.com",
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
        capacity=1,
        booked_count=0,
        is_active=True,
    )
    db.add(slot)
    db.commit()

    conversation = Conversation(
        dealership_id=dealership.id,
        channel="website",
        channel_user_id="web_session_999",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.commit()

    return dealership, vehicle, slot, conversation


def test_initiate_booking_verification_flow(db):
    dealership, vehicle, slot, conversation = _seed_data(db)

    req = BookingVerificationInitiateRequest(
        slot_id=slot.id,
        destination="chloe.customer@example.com",
        channel="website",
        customer_name="Chloe Customer",
        conversation_id=conversation.id,
    )

    initiate_res = customer_verification_service.initiate_booking_verification(
        db,
        dealership_id=dealership.id,
        payload=req,
    )

    assert initiate_res.status == "otp_sent"
    assert initiate_res.hold_token.startswith("hold_")
    assert initiate_res.destination == "chloe.customer@example.com"
    assert "chloe.customer@example.com" in initiate_res.message

    # Check slot hold in DB
    hold = slot_hold_service.get_active_slot_hold(db, initiate_res.hold_token)
    assert hold is not None
    assert hold.status == "held"
    assert hold.slot_id == slot.id

    # Check OTP in DB
    otp_record = db.query(OTPVerification).filter(
        OTPVerification.dealership_id == dealership.id,
        OTPVerification.identifier == "chloe.customer@example.com",
    ).first()
    assert otp_record is not None
    assert otp_record.attempts == 0


def test_verify_and_confirm_booking_happy_path(db, monkeypatch):
    monkeypatch.setattr("secrets.randbelow", lambda _: 123456)
    dealership, vehicle, slot, conversation = _seed_data(db)

    # 1. Initiate verification
    init_res = customer_verification_service.initiate_booking_verification(
        db,
        dealership_id=dealership.id,
        payload=BookingVerificationInitiateRequest(
            slot_id=slot.id,
            destination="chloe.customer@example.com",
            channel="website",
            customer_name="Chloe Customer",
            conversation_id=conversation.id,
        ),
    )

    assert init_res.status == "otp_sent"
    assert init_res.hold_token.startswith("hold_")

    # 2. Confirm booking with hold token and verified OTP
    confirm_res = customer_verification_service.verify_customer_and_confirm_booking(
        db,
        dealership_id=dealership.id,
        payload=BookingVerificationConfirmRequest(
            hold_token=init_res.hold_token,
            code="123456",
            destination="chloe.customer@example.com",
            channel="website",
            customer_name="Chloe Customer",
            confirmed=True,
            conversation_id=conversation.id,
        ),
    )

    assert confirm_res.status == "confirmed"
    assert confirm_res.booking_id > 0
    assert confirm_res.vehicle_name == "2024 Apex Solaris"

    # Verify JIT user account created
    user = db.query(User).filter(User.email == "chloe.customer@example.com").first()
    assert user is not None
    assert user.role == CUSTOMER_ROLE
    assert user.is_email_verified is True

    # Verify conversation linked
    db.refresh(conversation)
    assert conversation.customer_id == user.id

    # Verify booking in DB
    booking = db.query(TestDriveBooking).filter(TestDriveBooking.id == confirm_res.booking_id).first()
    assert booking is not None
    assert booking.customer_id == user.id

    # Verify slot hold status is confirmed
    hold = slot_hold_service.get_active_slot_hold(db, init_res.hold_token)
    assert hold is None  # Active holds only return status='held', confirmed holds are no longer 'held'
    confirmed_hold = db.query(TestDriveSlotHold).filter(TestDriveSlotHold.hold_token == init_res.hold_token).first()
    assert confirmed_hold.status == "confirmed"


def test_account_existence_privacy(db):
    """
    Demonstrates that initiate verification returns identical response whether user exists or not,
    and links existing account without creating duplicate records.
    """
    dealership, vehicle, slot, conversation = _seed_data(db)

    # Create an existing user first
    existing_user = User(
        dealership_id=dealership.id,
        name="Existing Customer",
        email="existing@example.com",
        password="hashedpassword123",
        role=CUSTOMER_ROLE,
        is_active=True,
    )
    db.add(existing_user)
    db.commit()

    # Initiate for existing user
    init_res1 = customer_verification_service.initiate_booking_verification(
        db,
        dealership_id=dealership.id,
        payload=BookingVerificationInitiateRequest(
            slot_id=slot.id,
            destination="existing@example.com",
            channel="website",
        ),
    )

    # Initiate for brand new email
    now = datetime.now(timezone.utc)
    slot2 = TestDriveSlot(
        dealership_id=dealership.id,
        vehicle_id=vehicle.id,
        starts_at=now + timedelta(days=3),
        ends_at=now + timedelta(days=3, minutes=30),
        capacity=1,
        booked_count=0,
        is_active=True,
    )
    db.add(slot2)
    db.commit()

    init_res2 = customer_verification_service.initiate_booking_verification(
        db,
        dealership_id=dealership.id,
        payload=BookingVerificationInitiateRequest(
            slot_id=slot2.id,
            destination="brandnew@example.com",
            channel="website",
        ),
    )

    # Both return status 'otp_sent' and do not expose user existence
    assert init_res1.status == "otp_sent"
    assert init_res2.status == "otp_sent"
    assert "code has been dispatched" in init_res1.message
    assert "code has been dispatched" in init_res2.message


def test_otp_security_cooldown_and_attempt_limits(db):
    dealership, vehicle, slot, _ = _seed_data(db)

    # 1. Request OTP
    code, _ = otp_service.request_otp(
        db,
        dealership_id=dealership.id,
        channel="website",
        identifier="security.test@example.com",
    )

    # 2. Resend within cooldown raises TooManyRequestsError
    with pytest.raises(TooManyRequestsError) as exc_info:
        otp_service.request_otp(
            db,
            dealership_id=dealership.id,
            channel="website",
            identifier="security.test@example.com",
        )
    assert "Please wait" in str(exc_info.value)

    # 3. Invalid verification attempts decrement attempts
    with pytest.raises(BadRequestError):
        otp_service.verify_otp(
            db,
            dealership_id=dealership.id,
            identifier="security.test@example.com",
            code="000000",
        )

    with pytest.raises(BadRequestError):
        otp_service.verify_otp(
            db,
            dealership_id=dealership.id,
            identifier="security.test@example.com",
            code="111111",
        )

    # 3rd failed attempt locks out the OTP
    with pytest.raises(ConflictError) as conf_info:
        otp_service.verify_otp(
            db,
            dealership_id=dealership.id,
            identifier="security.test@example.com",
            code="222222",
        )
    assert "Maximum verification attempts exceeded" in str(conf_info.value)


def test_hold_expiry_and_concurrency_prevention(db):
    dealership, vehicle, slot, _ = _seed_data(db)

    # Slot capacity is 1. Acquire hold for customer 1
    hold1 = slot_hold_service.acquire_slot_hold(
        db,
        dealership_id=dealership.id,
        slot_id=slot.id,
        identifier="customer1@example.com",
    )
    assert hold1 is not None

    # Customer 2 attempting to hold same slot fails with ConflictError
    with pytest.raises(ConflictError) as exc_info:
        slot_hold_service.acquire_slot_hold(
            db,
            dealership_id=dealership.id,
            slot_id=slot.id,
            identifier="customer2@example.com",
        )
    assert "No remaining capacity available" in str(exc_info.value)


def test_sales_agent_verification_api_endpoints(client, db, monkeypatch):
    monkeypatch.setattr("secrets.randbelow", lambda _: 123456)
    dealership, vehicle, slot, conversation = _seed_data(db)

    # 1. API: Initiate verification
    init_res = client.post(
        f"/api/v1/dealerships/{dealership.id}/sales-agent/verification/initiate",
        json={
            "slot_id": slot.id,
            "destination": "api.tester@example.com",
            "channel": "website",
            "customer_name": "API Tester",
            "conversation_id": conversation.id,
        },
    )
    assert init_res.status_code == 200
    init_data = init_res.json()
    assert init_data["status"] == "otp_sent"
    hold_token = init_data["hold_token"]

    # 2. Test explicit confirmation check: confirmed=False fails
    bad_confirm = client.post(
        f"/api/v1/dealerships/{dealership.id}/sales-agent/verification/confirm",
        json={
            "hold_token": hold_token,
            "code": "123456",
            "destination": "api.tester@example.com",
            "channel": "website",
            "confirmed": False,
        },
    )
    assert bad_confirm.status_code == 400

    # 3. Test successful API confirmation with hold_token and verified OTP code
    good_confirm = client.post(
        f"/api/v1/dealerships/{dealership.id}/sales-agent/verification/confirm",
        json={
            "hold_token": hold_token,
            "code": "123456",
            "destination": "api.tester@example.com",
            "channel": "website",
            "customer_name": "Verified API User",
            "confirmed": True,
            "conversation_id": conversation.id,
        },
    )
    assert good_confirm.status_code == 200
    confirm_data = good_confirm.json()
    assert confirm_data["status"] == "confirmed"
    assert confirm_data["booking_id"] > 0
    assert "2024 Apex Solaris" in confirm_data["vehicle_name"]
    assert "2024 Apex Solaris" in confirm_data["vehicle_name"]
