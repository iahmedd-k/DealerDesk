from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workspace import Dealership, TestDriveSlot


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_dealership_channel", "dealership_id", "channel"),
        Index("ix_conversations_channel_user", "channel", "channel_user_id"),
        Index(
            "uq_conversations_email_thread",
            "dealership_id",
            "channel",
            "external_thread_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(32), index=True)  # website, whatsapp, voice
    channel_user_id: Mapped[str] = mapped_column(String(320), index=True)  # email, phone number, or session token
    external_thread_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="active")  # active, closed, handed_off
    channel_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.id",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ix_conversation_messages_conv_id", "conversation_id"),
        Index(
            "uq_conversation_messages_external_id",
            "conversation_id",
            "external_message_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sender_type: Mapped[str] = mapped_column(String(32))  # customer, agent, staff, system
    sender_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text)
    external_message_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    channel_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class TestDriveSlotHold(Base):
    __tablename__ = "test_drive_slot_holds"
    __table_args__ = (
        Index("ix_slot_holds_slot_active", "slot_id", "status"),
        Index("ix_slot_holds_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("test_drive_slots.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    identifier: Mapped[str] = mapped_column(String(128), index=True)  # phone or email
    hold_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="held")  # held, confirmed, expired, released
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OTPVerification(Base):
    __tablename__ = "otp_verifications"
    __table_args__ = (
        Index("ix_otp_identifier_purpose", "identifier", "purpose"),
        Index("ix_otp_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(32))  # whatsapp, sms, email
    identifier: Mapped[str] = mapped_column(String(128), index=True)  # phone or email
    otp_hash: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(32), default="test_drive_booking")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TwilioWebhookReceipt(Base):
    __tablename__ = "twilio_webhook_receipts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    message_sid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="processing")
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TwilioDeliveryStatus(Base):
    __tablename__ = "twilio_delivery_statuses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    message_sid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    recipient: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
