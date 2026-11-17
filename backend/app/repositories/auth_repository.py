from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.user import (
    PasswordResetToken,
    RefreshToken,
    RevokedAccessToken,
    User,
    UserTokenVersion,
)
from app.models.workspace import StaffInvitation


def has_revoked_access_token(db: Session, token_hash: str, now: datetime) -> bool:
    return (
        db.scalar(
            select(RevokedAccessToken.id).where(
                RevokedAccessToken.token_hash == token_hash,
                RevokedAccessToken.expires_at > now,
            )
        )
        is not None
    )


def get_token_version(db: Session, user_id: int) -> int:
    return (
        db.scalar(
            select(UserTokenVersion.version).where(
                UserTokenVersion.user_id == user_id
            )
        )
        or 0
    )


def get_active_user(db: Session, user_id: int) -> User | None:
    user = db.get(User, user_id)
    return user if user is not None and user.is_active else None


def revoke_refresh_tokens(db: Session, user_id: int, now: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


def increment_token_version(db: Session, user_id: int) -> None:
    record = db.get(UserTokenVersion, user_id)
    if record is None:
        db.add(UserTokenVersion(user_id=user_id, version=1))
    else:
        record.version += 1


def save_refresh_token(db: Session, token: RefreshToken) -> RefreshToken:
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def revoke_access_token(
    db: Session,
    revoked_token: RevokedAccessToken,
    now: datetime,
    user_id: int,
) -> None:
    db.query(RevokedAccessToken).filter(
        RevokedAccessToken.expires_at <= now,
    ).delete(synchronize_session=False)
    db.add(revoked_token)
    revoke_refresh_tokens(db, user_id, now)
    db.commit()


def get_refresh_token_for_update(db: Session, token: str) -> RefreshToken | None:
    return db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token == token)
        .with_for_update()
    )


def rotate_refresh_token(
    db: Session,
    current: RefreshToken,
    replacement: RefreshToken,
    revoked_at: datetime,
) -> None:
    current.revoked_at = revoked_at
    db.add(replacement)
    db.commit()


def save_password_reset_token(
    db: Session,
    token: PasswordResetToken,
) -> PasswordResetToken:
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_password_reset_token(
    db: Session,
    token: str,
) -> PasswordResetToken | None:
    return db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.used_at.is_(None),
        )
    )


def delete_password_reset_token(db: Session, token: PasswordResetToken) -> None:
    db.delete(token)
    db.commit()


def get_invitation_by_token(
    db: Session,
    token: str,
) -> StaffInvitation | None:
    return db.scalar(
        select(StaffInvitation).where(
            StaffInvitation.activation_token == token,
            StaffInvitation.accepted_at.is_(None),
            StaffInvitation.revoked_at.is_(None),
        )
    )


def save_account_changes(db: Session, *entities: object) -> None:
    db.add_all(entities)
    db.commit()
