from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, SALES_REP_ROLE
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.models.workspace import Vehicle
from app.schemas.workspace import (
    VehicleCreateRequest,
    VehicleResponse,
    VehicleUpdateRequest,
)
from app.services import vehicle_service


router = APIRouter(prefix="/dealerships/{dealership_id}/vehicles", tags=["Vehicles"])


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    dealership_id: int,
    payload: VehicleCreateRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.create_vehicle(db, dealership_id, current_user, payload)


@router.get("", response_model=list[VehicleResponse])
def list_vehicles(
    dealership_id: int,
    include_archived_brands: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Vehicle]:
    return vehicle_service.list_vehicles(
        db,
        dealership_id,
        current_user,
        include_archived_brands=include_archived_brands,
    )


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.get_vehicle(db, dealership_id, vehicle_id, current_user)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    dealership_id: int,
    vehicle_id: int,
    payload: VehicleUpdateRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.update_vehicle(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        payload,
    )


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    vehicle_service.delete_vehicle(db, dealership_id, vehicle_id, current_user)


@router.patch("/{vehicle_id}/availability", response_model=VehicleResponse)
def update_vehicle_availability(
    dealership_id: int,
    vehicle_id: int,
    available: bool,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.update_vehicle_availability(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        available,
    )
