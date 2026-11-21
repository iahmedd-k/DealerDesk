import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_role_access
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.roles import (
    CUSTOMER_ROLE,
    DEALERSHIP_ADMIN_ROLE,
    DEALERSHIP_MANAGEMENT_ROLES,
)
from app.models.user import User
from app.models.workspace import StaffInvitation
from app.repositories import staff_repository, user_repository
from app.schemas.workspace import (
    StaffInvitationRequest,
    StaffInvitationResponse,
    StaffUpdateRequest,
)
from app.services import auth_service
from app.services.email_service import send_staff_invitation


def list_staff(
    db: Session,
    dealership_id: int,
    current_user: User,
) -> list[User]:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    return staff_repository.list_staff(db, dealership_id)


def invite_staff(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: StaffInvitationRequest,
) -> StaffInvitationResponse:
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)

    email = str(payload.email).lower()
    now = datetime.now(timezone.utc)
    temporary_password = secrets.token_urlsafe(16)
    invited_user = user_repository.get_by_email(db, email)
    invitation: StaffInvitation
    try:
        if invited_user is not None:
            if (
                invited_user.dealership_id != dealership_id
                or invited_user.role == CUSTOMER_ROLE
            ):
                raise ConflictError("Email is already registered")
            invitation = staff_repository.get_latest_invitation_for_user(
                db, invited_user.id
            )
            if (
                invitation is None
                or (invited_user.is_active and invitation.accepted_at is not None)
                or (
                    invited_user.is_active
                    and invitation.revoked_at is None
                    and invitation.accepted_at is None
                    and _utc(invitation.expires_at) > now
                )
            ):
                raise ConflictError("Email is already registered")
            invited_user.name = payload.name
            invited_user.role = payload.role
            invited_user.password = auth_service.hash_password(temporary_password)
            invited_user.is_active = True
            invited_user.must_change_password = True
            auth_service.revoke_user_refresh_tokens(db, invited_user.id)
            auth_service.invalidate_user_access_tokens(db, invited_user.id)
            invitation.invited_by_user_id = current_user.id
            invitation.email = email
            invitation.role = payload.role
            invitation.activation_token = secrets.token_urlsafe(48)
            invitation.expires_at = now + timedelta(days=2)
            invitation.accepted_at = None
            invitation.revoked_at = None
            staff_repository.save(db, invited_user, invitation)
        else:
            invited_user, invitation = staff_repository.create_invitation(
                db,
                dealership_id=dealership_id,
                inviter_id=current_user.id,
                name=payload.name,
                email=email,
                role=payload.role,
                password=auth_service.hash_password(temporary_password),
                activation_token=secrets.token_urlsafe(48),
                expires_at=now + timedelta(days=2),
            )
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Unable to create staff invitation") from exc

    dealership = staff_repository.get_dealership(db, dealership_id)
    delivery_status = send_staff_invitation(
        recipient=invitation.email,
        dealership_name=dealership.name if dealership else "your dealership",
        temporary_password=temporary_password,
        activation_token=invitation.activation_token,
    )
    return StaffInvitationResponse(
        id=invitation.id,
        user_id=invited_user.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        delivery_status=delivery_status,
        status="pending",
    )


def update_staff(
    db: Session,
    dealership_id: int,
    user_id: int,
    current_user: User,
    payload: StaffUpdateRequest,
) -> User:
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)
    user = _get_staff_user(db, dealership_id, user_id)
    if (
        user.role == DEALERSHIP_ADMIN_ROLE
        and user.is_active
        and (payload.role is not None or payload.is_active is False)
    ):
        _ensure_another_active_admin_exists(db, dealership_id, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value)
    if payload.is_active is False:
        auth_service.revoke_user_refresh_tokens(db, user.id)
        auth_service.invalidate_user_access_tokens(db, user.id)
    staff_repository.save(db, user)
    return user


def list_invitations(
    db: Session,
    dealership_id: int,
    current_user: User,
) -> list[StaffInvitationResponse]:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    invitations = staff_repository.list_invitations(db, dealership_id)
    return [
        StaffInvitationResponse(
            id=invitation.id,
            user_id=invitation.user_id,
            email=invitation.email,
            role=invitation.role,
            expires_at=invitation.expires_at,
            delivery_status="accepted" if invitation.accepted_at else "pending",
            status=_invitation_status(invitation),
        )
        for invitation in invitations
    ]


def revoke_invitation(
    db: Session,
    dealership_id: int,
    invitation_id: int,
    current_user: User,
) -> None:
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)
    invitation = staff_repository.get_invitation(db, dealership_id, invitation_id)
    if invitation is None:
        raise NotFoundError("Invitation not found")
    if invitation.accepted_at is not None:
        raise ConflictError("Accepted invitations cannot be revoked")
    invitation.revoked_at = datetime.now(timezone.utc)
    invited_user = user_repository.get_by_id(db, invitation.user_id)
    if invited_user is not None:
        invited_user.is_active = False
        auth_service.revoke_user_refresh_tokens(db, invited_user.id)
        auth_service.invalidate_user_access_tokens(db, invited_user.id)
        staff_repository.save(db, invitation, invited_user)
    else:
        staff_repository.save(db, invitation)


def remove_staff(
    db: Session,
    dealership_id: int,
    user_id: int,
    current_user: User,
) -> None:
    ensure_dealership_role_access(current_user, dealership_id, DEALERSHIP_ADMIN_ROLE)
    user = _get_staff_user(db, dealership_id, user_id)
    if user.id == current_user.id:
        raise BadRequestError("A dealership admin cannot remove themselves")
    if user.role == DEALERSHIP_ADMIN_ROLE and user.is_active:
        _ensure_another_active_admin_exists(db, dealership_id, user.id)
    user.is_active = False
    auth_service.revoke_user_refresh_tokens(db, user.id)
    auth_service.invalidate_user_access_tokens(db, user.id)
    staff_repository.save(db, user)


def get_staff(
    db: Session,
    dealership_id: int,
    user_id: int,
    current_user: User,
) -> User:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    return _get_staff_user(db, dealership_id, user_id)


def _get_staff_user(db: Session, dealership_id: int, user_id: int) -> User:
    user = staff_repository.get_staff_user(db, dealership_id, user_id)
    if user is None:
        raise NotFoundError("Staff member not found")
    return user


def _ensure_another_active_admin_exists(
    db: Session,
    dealership_id: int,
    excluded_user_id: int,
) -> None:
    staff_repository.lock_dealership(db, dealership_id)
    if not staff_repository.has_another_active_admin(
        db,
        dealership_id,
        excluded_user_id,
    ):
        raise ConflictError(
            "The dealership must retain at least one active administrator"
        )


def _invitation_status(invitation: StaffInvitation) -> str:
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.revoked_at is not None:
        return "revoked"
    if _utc(invitation.expires_at) <= datetime.now(timezone.utc):
        return "expired"
    return "pending"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
