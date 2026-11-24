import secrets
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_admin
from app.core.errors import (
    BadRequestError,
    ConflictError,
    ServiceUnavailableError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from app.core.roles import (
    CUSTOMER_ROLE,
    DEALERDESK_ADMIN_ROLE,
    DEALERSHIP_ADMIN_ROLE,
)
from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    RevokedAccessToken,
    User,
)
from app.repositories import auth_repository, user_repository
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    SignUpRequest,
    TokenResponse,
)
from app.schemas.user import UserUpdateRequest
from app.schemas.workspace import ActivationRequest, ChangePasswordRequest
from app.services import auth_service
from app.services.email_service import send_email_verification, send_password_reset


PASSWORD_RESET_MESSAGE = (
    "If the account exists, reset instructions will be sent "
    "when email delivery is available"
)
logger = logging.getLogger(__name__)


def signup(db: Session, payload: SignUpRequest) -> User:
    email = str(payload.email).lower()
    if user_repository.get_by_email(db, email):
        raise ConflictError("Email already registered")
    try:
        new_user = user_repository.create(
            db,
            name=payload.name,
            email=email,
            password=auth_service.hash_password(payload.password),
            role=CUSTOMER_ROLE,
        )
        raw_verification_token = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        verification_token = EmailVerificationToken(
            user_id=new_user.id,
            token_hash=auth_service.hash_token(raw_verification_token),
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        db.add(verification_token)
        db.commit()
        send_email_verification(
            recipient=new_user.email,
            verification_token=raw_verification_token,
        )
        return new_user
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Email already registered") from exc


def login(db: Session, payload: LoginRequest) -> TokenResponse:
    user = user_repository.get_by_email(db, str(payload.email).lower())
    now = datetime.now(timezone.utc)

    # Brute-force protection / account lockout check
    if user is not None and user.locked_until is not None:
        locked_until_utc = _utc(user.locked_until)
        if locked_until_utc > now:
            remaining_minutes = max(1, int((locked_until_utc - now).total_seconds() / 60) + 1)
            raise UnauthorizedError(
                f"Account temporarily locked due to repeated failed login attempts. Try again in {remaining_minutes} minutes.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            user.locked_until = None
            user.failed_login_attempts = 0
            user_repository.save(db, user)

    if (
        user is None
        or not user.is_active
        or not auth_service.verify_password(payload.password, user.password)
    ):
        if user is not None and user.is_active:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
                logger.warning(
                    "auth.account_locked",
                    extra={"user_id": user.id, "email": user.email},
                )
            user_repository.save(db, user)
        raise UnauthorizedError(
            "Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed login count on successful authentication
    if (user.failed_login_attempts or 0) > 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        user_repository.save(db, user)

    try:
        access_token = auth_service.create_access_token(
            user.id,
            auth_service.get_user_token_version(db, user.id),
        )
    except RuntimeError as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    raw_refresh_token = secrets.token_urlsafe(48)
    refresh_token = RefreshToken(
        user_id=user.id,
        token=auth_service.hash_token(raw_refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    try:
        auth_repository.save_refresh_token(db, refresh_token)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Unable to create refresh token") from exc
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


def logout(
    db: Session,
    token: str,
    current_user: User,
) -> None:
    now = datetime.now(timezone.utc)
    revoked_token = RevokedAccessToken(
        user_id=current_user.id,
        token_hash=auth_service.hash_token(token),
        expires_at=auth_service.get_access_token_expiry(token),
    )
    auth_repository.revoke_access_token(
        db,
        revoked_token,
        now,
        current_user.id,
    )


def list_users(db: Session, current_user: User) -> list[User]:
    ensure_dealership_admin(current_user)
    if current_user.dealership_id is None:
        if current_user.role == DEALERDESK_ADMIN_ROLE:
            return user_repository.list_all(db)
        return []
    return user_repository.list_for_dealership(db, current_user.dealership_id)


def update_current_user(
    db: Session,
    current_user: User,
    payload: UserUpdateRequest,
) -> User:
    if payload.email is not None:
        normalized_email = str(payload.email).lower()
        existing = user_repository.get_by_email(db, normalized_email)
        if existing is not None and existing.id != current_user.id:
            raise ConflictError("Email already registered")
        current_user.email = normalized_email
    if payload.name is not None:
        current_user.name = payload.name
    try:
        return user_repository.save(db, current_user, refresh=True)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Email already registered") from exc


def delete_current_user(db: Session, current_user: User) -> None:
    if (
        current_user.role == DEALERSHIP_ADMIN_ROLE
        and current_user.dealership_id is not None
    ):
        dealership_id = current_user.dealership_id
        user_repository.lock_dealership(db, dealership_id)
        if not user_repository.has_another_active_admin(
            db,
            dealership_id,
            current_user.id,
        ):
            raise ConflictError(
                "The dealership must retain at least one active administrator"
            )
    current_user.is_active = False
    auth_service.revoke_user_refresh_tokens(db, current_user.id)
    auth_service.invalidate_user_access_tokens(db, current_user.id)
    user_repository.save(db, current_user)


def refresh_access_token(
    db: Session,
    payload: RefreshTokenRequest,
) -> TokenResponse:
    now = datetime.now(timezone.utc)
    stored = auth_repository.get_refresh_token_for_update(
        db,
        auth_service.hash_token(payload.refresh_token),
    )
    if (
        stored is None
        or stored.revoked_at is not None
        or _utc(stored.expires_at) <= now
    ):
        raise UnauthorizedError("Invalid or expired refresh token")
    user = user_repository.get_by_id(db, stored.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User account is unavailable")
    try:
        access_token = auth_service.create_access_token(
            user.id,
            auth_service.get_user_token_version(db, user.id),
        )
    except RuntimeError as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    raw_refresh_token = secrets.token_urlsafe(48)
    replacement = RefreshToken(
        user_id=user.id,
        token=auth_service.hash_token(raw_refresh_token),
        expires_at=now + timedelta(days=30),
    )
    auth_repository.rotate_refresh_token(db, stored, replacement, now)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


def request_password_reset(
    db: Session,
    payload: PasswordResetRequest,
) -> dict[str, str]:
    user = user_repository.get_by_email(db, str(payload.email).lower())
    if user is not None and user.is_active:
        raw_reset_token = secrets.token_urlsafe(48)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=auth_service.hash_token(raw_reset_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        auth_repository.save_password_reset_token(db, reset_token)
        delivery_status = send_password_reset(
            recipient=user.email,
            reset_token=raw_reset_token,
        )
        if delivery_status != "email_sent":
            auth_repository.delete_password_reset_token(db, reset_token)
            logger.error(
                "Password reset email delivery failed",
                extra={"user_id": user.id, "delivery_status": delivery_status},
            )
    return {"message": PASSWORD_RESET_MESSAGE}


def reset_password(
    db: Session,
    payload: PasswordResetConfirm,
) -> dict[str, str]:
    reset = auth_repository.get_password_reset_token(
        db,
        auth_service.hash_token(payload.token),
    )
    if reset is None or _utc(reset.expires_at) <= datetime.now(timezone.utc):
        raise BadRequestError("Invalid or expired password reset token")
    user = user_repository.get_by_id(db, reset.user_id)
    if user is None or not user.is_active:
        raise BadRequestError("User account is unavailable")
    user.password = auth_service.hash_password(payload.new_password)
    user.must_change_password = False
    reset.used_at = datetime.now(timezone.utc)
    auth_service.revoke_user_refresh_tokens(db, user.id)
    auth_service.invalidate_user_access_tokens(db, user.id)
    auth_repository.save_account_changes(db, user, reset)
    return {"message": "Password reset successfully"}


def activate_invitation(db: Session, payload: ActivationRequest) -> User:
    invitation = auth_repository.get_invitation_by_token(
        db,
        auth_service.hash_token(payload.token),
    )
    if invitation is None or _utc(invitation.expires_at) <= datetime.now(timezone.utc):
        raise BadRequestError("Invitation is invalid or expired")
    user = user_repository.get_by_id(db, invitation.user_id)
    if user is None or not user.is_active:
        raise BadRequestError("Invited account is unavailable")
    user.password = auth_service.hash_password(payload.password)
    user.must_change_password = False
    invitation.accepted_at = datetime.now(timezone.utc)
    auth_service.revoke_user_refresh_tokens(db, user.id)
    auth_service.invalidate_user_access_tokens(db, user.id)
    auth_repository.save_account_changes(db, user, invitation)
    return user


def change_password(
    db: Session,
    current_user: User,
    payload: ChangePasswordRequest,
) -> User:
    if not auth_service.verify_password(
        payload.current_password,
        current_user.password,
    ):
        raise BadRequestError("Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise UnprocessableEntityError("New password must be different")
    current_user.password = auth_service.hash_password(payload.new_password)
    current_user.must_change_password = False
    auth_service.revoke_user_refresh_tokens(db, current_user.id)
    auth_service.invalidate_user_access_tokens(db, current_user.id)
    return user_repository.save(db, current_user, refresh=True)


def verify_email(db: Session, token: str) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    hashed_token = auth_service.hash_token(token)
    verification = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == hashed_token,
            EmailVerificationToken.used_at.is_(None),
        )
        .first()
    )
    if verification is None or _utc(verification.expires_at) <= now:
        raise BadRequestError("Invalid or expired email verification token")

    user = user_repository.get_by_id(db, verification.user_id)
    if user is None or not user.is_active:
        raise BadRequestError("User account not found or inactive")

    user.is_email_verified = True
    verification.used_at = now
    db.commit()
    return {"message": "Email address verified successfully"}


def resend_verification_email(db: Session, email: str) -> dict[str, str]:
    user = user_repository.get_by_email(db, str(email).lower())
    if user is not None and user.is_active and not user.is_email_verified:
        now = datetime.now(timezone.utc)
        raw_token = secrets.token_urlsafe(48)
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token_hash=auth_service.hash_token(raw_token),
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        db.add(verification_token)
        db.commit()
        send_email_verification(
            recipient=user.email,
            verification_token=raw_token,
        )
    return {
        "message": "If an unverified account exists for this email, a verification link has been sent"
    }


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
