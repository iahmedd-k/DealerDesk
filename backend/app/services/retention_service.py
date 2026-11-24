import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.idempotency import IdempotencyKey
from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    RevokedAccessToken,
)

logger = logging.getLogger(__name__)


def cleanup_expired_data(
    db: Session,
    dry_run: bool = False,
    audit_retention_days: int = 365,
) -> dict[str, Any]:
    """
    Cleans up expired and tombstoned operational data across DealerDesk tables:
    - Expired idempotency replay keys
    - Expired and revoked JWT refresh tokens
    - Expired access token revocation entries
    - Expired and used password reset tokens
    - Expired and used email verification tokens
    - Aged audit logs past retention threshold
    """
    now = datetime.now(timezone.utc)
    audit_threshold = now - timedelta(days=audit_retention_days)

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
    }

    counts: dict[str, int] = {}
    for entity_name, query in queries.items():
        count = query.count()
        counts[entity_name] = count
        if not dry_run and count > 0:
            query.delete(synchronize_session=False)

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
