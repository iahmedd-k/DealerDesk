from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.roles import (
    DEALERSHIP_ADMIN_ROLE,
    DEALERSHIP_MANAGEMENT_ROLES,
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
from app.services import staff_service


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
