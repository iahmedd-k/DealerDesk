"""Database models."""

from app.models.audit import AuditLog
from app.models.channel import (
    Conversation,
    ConversationMessage,
    OTPVerification,
    TestDriveSlotHold,
)
from app.models.idempotency import IdempotencyKey
from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    RevokedAccessToken,
    User,
    UserTokenVersion,
)
from app.models.workspace import (
    Brand,
    CustomerLead,
    Dealership,
    KnowledgeChunk,
    KnowledgeDocument,
    LeadActivity,
    NotificationDelivery,
    OutboxEvent,
    StaffInvitation,
    TestDriveBooking,
    TestDriveSettings,
    TestDriveSlot,
    Vehicle,
    VehicleImage,
    VehicleStatusHistory,
)

__all__ = [
    "AuditLog",
    "Brand",
    "Conversation",
    "ConversationMessage",
    "CustomerLead",
    "Dealership",
    "EmailVerificationToken",
    "IdempotencyKey",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "LeadActivity",
    "NotificationDelivery",
    "OTPVerification",
    "OutboxEvent",
    "PasswordResetToken",
    "RefreshToken",
    "RevokedAccessToken",
    "StaffInvitation",
    "TestDriveBooking",
    "TestDriveSettings",
    "TestDriveSlot",
    "TestDriveSlotHold",
    "User",
    "UserTokenVersion",
    "Vehicle",
    "VehicleImage",
    "VehicleStatusHistory",
]
