"""Database models."""

from app.models.audit import AuditLog
from app.models.channel import (
    Conversation,
    ConversationMessage,
    OTPVerification,
    TestDriveSlotHold,
    TwilioDeliveryStatus,
    TwilioWebhookReceipt,
)
from app.models.idempotency import IdempotencyKey
from app.models.quote import LeadQuote
from app.models.gmail import GmailMailboxConnection
from app.models.service import ServiceAppointment, ServiceWorkOrder, VehicleWarranty
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
    "GmailMailboxConnection",
    "IdempotencyKey",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "LeadQuote",
    "LeadActivity",
    "NotificationDelivery",
    "OTPVerification",
    "OutboxEvent",
    "PasswordResetToken",
    "RefreshToken",
    "RevokedAccessToken",
    "ServiceAppointment",
    "ServiceWorkOrder",
    "StaffInvitation",
    "TestDriveBooking",
    "TestDriveSettings",
    "TestDriveSlot",
    "TestDriveSlotHold",
    "TwilioDeliveryStatus",
    "TwilioWebhookReceipt",
    "User",
    "UserTokenVersion",
    "Vehicle",
    "VehicleImage",
    "VehicleStatusHistory",
    "VehicleWarranty",
]
