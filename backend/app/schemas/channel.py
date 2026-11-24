from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    WEBSITE = "website"
    WHATSAPP = "whatsapp"
    VOICE = "voice"


class MessageSenderType(str, Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    STAFF = "staff"
    SYSTEM = "system"


class ChannelEvent(BaseModel):
    dealership_id: int = Field(..., description="ID of the target dealership")
    channel: ChannelType = Field(..., description="Inbound communication channel")
    channel_user_id: str = Field(..., description="Unique customer identifier on this channel (phone, session ID)")
    message: str = Field(..., description="Raw text or transcribed message content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Channel-specific headers or delivery payload")


class ConversationResponse(BaseModel):
    id: int
    dealership_id: int
    channel: str
    channel_user_id: str
    customer_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_type: str
    sender_id: int | None = None
    content: str
    channel_metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SlotHoldCreate(BaseModel):
    slot_id: int = Field(..., description="ID of the test-drive slot to temporarily hold")
    identifier: str = Field(..., description="Customer contact identifier (phone or email)")
    duration_minutes: int = Field(default=10, ge=3, le=30, description="Hold lease duration in minutes")


class SlotHoldResponse(BaseModel):
    id: int
    dealership_id: int
    slot_id: int
    hold_token: str
    identifier: str
    status: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class OTPRequest(BaseModel):
    channel: str = Field(..., description="Channel to deliver the OTP (whatsapp, sms, email)")
    identifier: str = Field(..., description="Target phone number or email address")
    purpose: str = Field(default="test_drive_booking", description="Purpose of verification")


class OTPVerifyRequest(BaseModel):
    identifier: str = Field(..., description="Target phone number or email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    purpose: str = Field(default="test_drive_booking", description="Purpose of verification")


class OTPVerificationResponse(BaseModel):
    success: bool
    message: str
    identifier: str
    verified: bool


class BookingVerificationInitiateRequest(BaseModel):
    slot_id: int = Field(..., description="ID of the test-drive slot")
    destination: str = Field(..., min_length=3, max_length=128, description="Customer phone number or email address")
    channel: str = Field(default="website", description="Channel requesting verification (website, whatsapp, voice, sms)")
    customer_name: str | None = Field(default=None, max_length=100, description="Customer full name")
    conversation_id: int | None = Field(default=None, description="Optional active conversation session ID")


class BookingVerificationInitiateResponse(BaseModel):
    status: str
    hold_token: str
    slot_id: int
    destination: str
    channel: str
    expires_at: str
    message: str


class BookingVerificationConfirmRequest(BaseModel):
    hold_token: str = Field(..., min_length=10, description="Hold reservation token")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    destination: str = Field(..., min_length=3, max_length=128, description="Customer phone or email used during initiation")
    channel: str = Field(default="website", description="Communication channel")
    customer_name: str | None = Field(default=None, max_length=100, description="Customer full name")
    notes: str | None = Field(default=None, max_length=500, description="Customer booking notes")
    confirmed: bool = Field(default=True, description="Explicit customer confirmation to book the slot")
    conversation_id: int | None = Field(default=None, description="Optional active conversation session ID")


class BookingVerificationConfirmResponse(BaseModel):
    status: str
    booking_id: int
    customer_id: int
    slot_id: int
    vehicle_id: int
    vehicle_name: str
    starts_at: str
    ends_at: str
    message: str

