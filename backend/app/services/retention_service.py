import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

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
)
from app.models.workspace import CustomerLead
from app.services.conversation_service import scrub_sensitive_pii

logger = logging.getLogger(__name__)


def cleanup_expired_data(
    db: Session,
    dry_run: bool = False,
    audit_retention_days: int = 365,
    lead_retention_days: int = 365,
    transcript_redaction_days: int = 90,
    transcript_retention_days: int = 365,
) -> dict[str, Any]:
    """
    Cleans up expired and tombstoned operational data across DealerDesk tables:
    - Expired idempotency replay keys
    - Expired and revoked JWT refresh tokens
    - Expired access token revocation entries
    - Expired and used password reset tokens
    - Expired and used email verification tokens
    - Expired OTP verifications and expired/released slot holds
    - Aged audit logs past retention threshold
    - Closed or unconsented customer leads past lead retention threshold
    - Message-level PII redaction for aged closed conversation transcripts
    - Closed conversation transcripts past transcript retention threshold
    """
    now = datetime.now(timezone.utc)
    audit_threshold = now - timedelta(days=audit_retention_days)
    lead_threshold = now - timedelta(days=lead_retention_days)
    transcript_redact_threshold = now - timedelta(days=transcript_redaction_days)
    transcript_delete_threshold = now - timedelta(days=transcript_retention_days)

    queries = {
        "idempotency_keys": db.query(IdempotencyKey).filter(
            IdempotencyKey.expires_at < now
        ),
        "revoked_access_tokens": db.query(RevokedAccessToken).filter(
            RevokedAccessToken.expires_at < now
        ),
        "refresh_tokens": db.query(RefreshToken).filter(
            (RefreshToken.expires_at < now) | (RefreshToken.revoked_at.is_not(None))
        ),
        "password_reset_tokens": db.query(PasswordResetToken).filter(
            (PasswordResetToken.expires_at < now)
            | (PasswordResetToken.used_at.is_not(None))
        ),
        "email_verification_tokens": db.query(EmailVerificationToken).filter(
            (EmailVerificationToken.expires_at < now)
            | (EmailVerificationToken.used_at.is_not(None))
        ),
        "audit_logs": db.query(AuditLog).filter(
            AuditLog.created_at < audit_threshold
        ),
        "customer_leads": db.query(CustomerLead).filter(
            CustomerLead.updated_at < lead_threshold,
            (CustomerLead.status.in_(["won", "lost"])) | (CustomerLead.consent_to_contact.is_(False)),
        ),
        "otp_verifications": db.query(OTPVerification).filter(
            OTPVerification.expires_at < now
        ),
        "slot_holds": db.query(TestDriveSlotHold).filter(
            TestDriveSlotHold.expires_at < now
        ),
        "closed_conversations": db.query(Conversation).filter(
            Conversation.status == "closed",
            Conversation.updated_at < transcript_delete_threshold,
        ),
    }

    counts: dict[str, int] = {}
    for entity_name, query in queries.items():
        count = query.count()
        counts[entity_name] = count
        if not dry_run and count > 0:
            query.delete(synchronize_session=False)

    # Message-level PII redaction for aged closed conversations
    redacted_messages = 0
    aged_messages = (
        db.query(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .filter(
            Conversation.status == "closed",
            ConversationMessage.created_at < transcript_redact_threshold,
            ConversationMessage.sender_type != "system",
        )
        .all()
    )
    for msg in aged_messages:
        meta = dict(msg.channel_metadata or {})
        if meta.get("pii_redacted") or meta.get("redacted"):
            continue
        scrubbed, changed = scrub_sensitive_pii(msg.content, include_contact_pii=True)
        if changed:
            redacted_messages += 1
            if not dry_run:
                msg.content = scrubbed
                meta["pii_redacted"] = True
                meta["pii_redacted_at"] = now.isoformat()
                msg.channel_metadata = meta

    counts["redacted_transcript_messages"] = redacted_messages

    if not dry_run:
        db.commit()

    logger.info(
        "Data retention cleanup completed",
        extra={"dry_run": dry_run, "counts": counts},
    )
    return {
        "dry_run": dry_run,
        "executed_at": now.isoformat(),
        "cleaned_counts": counts,
        "total_pruned": sum(counts.values()),
    }
