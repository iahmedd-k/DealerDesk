from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_role_access
from app.core.errors import NotFoundError
from app.core.roles import (
    DEALERSHIP_ADMIN_ROLE,
    DEALERSHIP_MANAGEMENT_ROLES,
    STAFF_ROLES,
)
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.schemas.user import UserResponse
from app.schemas.workspace import (
    StaffInvitationRequest,
    StaffInvitationResponse,
    StaffUpdateRequest,
)
from app.services import audit_service, staff_service


router = APIRouter(prefix="/dealerships/{dealership_id}/staff", tags=["Staff"])


@router.get("", response_model=list[UserResponse])
def list_staff(
    dealership_id: int,
    current_user: User = Depends(
        require_dealership_roles(*DEALERSHIP_MANAGEMENT_ROLES)
    ),
    db: Session = Depends(get_db),
) -> list[User]:
    return staff_service.list_staff(db, dealership_id, current_user)


@router.post(
    "/invite",
    response_model=StaffInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_staff(
    dealership_id: int,
    payload: StaffInvitationRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> StaffInvitationResponse:
    return staff_service.invite_staff(db, dealership_id, current_user, payload)


@router.patch("/{user_id}", response_model=UserResponse)
def update_staff(
    dealership_id: int,
    user_id: int,
    payload: StaffUpdateRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> User:
    return staff_service.update_staff(
        db,
        dealership_id,
        user_id,
        current_user,
        payload,
    )


class StaffAvailabilityUpdateRequest(BaseModel):
    is_available: bool
    availability_note: str | None = Field(default=None, max_length=255)


@router.patch("/{user_id}/availability", response_model=UserResponse)
def update_staff_availability(
    dealership_id: int,
    user_id: int,
    payload: StaffAvailabilityUpdateRequest,
    request: Request,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> User:
    if current_user.id != user_id:
        ensure_dealership_role_access(current_user, dealership_id, *DEALERSHIP_MANAGEMENT_ROLES)
    target = (
        db.query(User)
        .filter(User.id == user_id, User.dealership_id == dealership_id)
        .first()
    )
    if target is None:
        raise NotFoundError("Staff member not found")
    target.is_available = payload.is_available
    target.availability_note = payload.availability_note
    db.commit()
    db.refresh(target)
    audit_service.log_event(
        db,
        action="staff.availability_changed",
        resource_type="user",
        resource_id=str(target.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={
            "is_available": target.is_available,
            "availability_note": target.availability_note,
        },
    )
    return target


@router.get("/invitations", response_model=list[StaffInvitationResponse])
def list_invitations(
    dealership_id: int,
    current_user: User = Depends(
        require_dealership_roles(*DEALERSHIP_MANAGEMENT_ROLES)
    ),
    db: Session = Depends(get_db),
) -> list[StaffInvitationResponse]:
    return staff_service.list_invitations(db, dealership_id, current_user)


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    dealership_id: int,
    invitation_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    staff_service.revoke_invitation(
        db,
        dealership_id,
        invitation_id,
        current_user,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_staff(
    dealership_id: int,
    user_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    staff_service.remove_staff(db, dealership_id, user_id, current_user)


@router.get("/{user_id}", response_model=UserResponse)
def get_staff(
    dealership_id: int,
    user_id: int,
    current_user: User = Depends(
        require_dealership_roles(*DEALERSHIP_MANAGEMENT_ROLES)
    ),
    db: Session = Depends(get_db),
) -> User:
    return staff_service.get_staff(db, dealership_id, user_id, current_user)
