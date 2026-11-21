from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_access
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_dealerdesk_admin
from app.models.user import User
from app.models.workspace import Dealership
from app.schemas.user import UserResponse
from app.schemas.workspace import (
    DealershipDetailedResponse,
    DealershipRegistrationRequest,
    DealershipResponse,
    DealershipSubscriptionUpdateRequest,
    DealershipUpdateRequest,
    PlatformMetricsResponse,
)
from app.services import dealership_service


router = APIRouter(prefix="/dealerships", tags=["Dealerships"])


@router.get("/metrics", response_model=PlatformMetricsResponse)
def get_platform_metrics(
    current_user: User = Depends(require_dealerdesk_admin),
    db: Session = Depends(get_db),
) -> dict:
    return dealership_service.get_platform_metrics(db)


@router.get("/public", response_model=list[DealershipResponse])
def list_public_dealerships(db: Session = Depends(get_db)) -> list[Dealership]:
    return dealership_service.list_active_dealerships(db)


@router.get("", response_model=list[DealershipDetailedResponse])
def list_dealerships(
    current_user: User = Depends(require_dealerdesk_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    return dealership_service.list_detailed_dealerships(db)


@router.patch("/{dealership_id}/subscription", response_model=DealershipResponse)
def update_dealership_subscription(
    dealership_id: int,
    payload: DealershipSubscriptionUpdateRequest,
    current_user: User = Depends(require_dealerdesk_admin),
    db: Session = Depends(get_db),
) -> Dealership:
    return dealership_service.update_subscription(db, dealership_id, payload)


@router.get("/{dealership_id}", response_model=DealershipResponse)
def get_dealership(
    dealership_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dealership:
    ensure_dealership_access(current_user, dealership_id)
    return dealership_service.get_active_dealership(db, dealership_id)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_dealership(
    payload: DealershipRegistrationRequest,
    db: Session = Depends(get_db),
) -> User:
    return dealership_service.register_dealership(db, payload)


@router.patch("/{dealership_id}", response_model=DealershipResponse)
def update_dealership(
    dealership_id: int,
    payload: DealershipUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dealership:
    return dealership_service.update_dealership(db, dealership_id, current_user, payload)


@router.delete("/{dealership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dealership(
    dealership_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    dealership_service.delete_dealership(db, dealership_id, current_user)
