import math
from decimal import Decimal
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, SALES_REP_ROLE
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.models.workspace import Vehicle, VehicleImage
from app.schemas.workspace import (
    VehicleCreateRequest,
    VehicleImageResponse,
    VehicleImageUpdateRequest,
    VehicleResponse,
    VehicleStatusHistoryResponse,
    VehicleStatusTransitionRequest,
    VehicleUpdateRequest,
)
from app.services import vehicle_service
from app.services import vehicle_image_service


router = APIRouter(prefix="/dealerships/{dealership_id}/vehicles", tags=["Vehicles"])


@router.get("/public", response_model=list[VehicleResponse])
def list_public_vehicles(
    dealership_id: int,
    response: Response,
    brand_id: int | None = Query(default=None, description="Filter by brand ID"),
    min_price: Decimal | None = Query(default=None, ge=0, description="Minimum price filter"),
    max_price: Decimal | None = Query(default=None, ge=0, description="Maximum price filter"),
    search: str | None = Query(default=None, description="Search keyword in model, make, variant, or stock number"),
    sort_by: str | None = Query(default=None, description="Field to sort by (price, year, model)"),
    order: str = Query(default="asc", pattern=r"^(asc|desc)$", description="Sort order ('asc' or 'desc')"),
    page: int | None = Query(default=None, ge=1, description="Page number starting at 1"),
    page_size: int | None = Query(default=None, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> list[Vehicle]:
    vehicles = vehicle_service.list_public_vehicles(
        db,
        dealership_id,
        brand_id=brand_id,
        min_price=min_price,
        max_price=max_price,
        search=search,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
    if page is not None and page_size is not None:
        total = vehicle_service.count_vehicles(
            db,
            dealership_id,
            brand_id=brand_id,
            min_price=min_price,
            max_price=max_price,
            is_available=True,
            search=search,
        )
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Page"] = str(page)
        response.headers["X-Page-Size"] = str(page_size)
        response.headers["X-Total-Pages"] = str(math.ceil(total / page_size) if page_size > 0 else 1)
    return vehicles


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
    response: Response,
    include_archived_brands: bool = False,
    brand_id: int | None = Query(default=None, description="Filter by brand ID"),
    min_price: Decimal | None = Query(default=None, ge=0, description="Minimum price filter"),
    max_price: Decimal | None = Query(default=None, ge=0, description="Maximum price filter"),
    status: str | None = Query(default=None, description="Filter by lifecycle status (available, reserved, sold, in_transit, unavailable)"),
    is_available: bool | None = Query(default=None, description="Filter by availability status"),
    test_drive_enabled: bool | None = Query(default=None, description="Filter by test drive availability"),
    search: str | None = Query(default=None, description="Search keyword in model, make, variant, or stock number"),
    sort_by: str | None = Query(default=None, description="Field to sort by (price, year, model)"),
    order: str = Query(default="asc", pattern=r"^(asc|desc)$", description="Sort order ('asc' or 'desc')"),
    page: int | None = Query(default=None, ge=1, description="Page number starting at 1"),
    page_size: int | None = Query(default=None, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Vehicle]:
    vehicles = vehicle_service.list_vehicles(
        db,
        dealership_id,
        current_user,
        include_archived_brands=include_archived_brands,
        brand_id=brand_id,
        min_price=min_price,
        max_price=max_price,
        status=status,
        is_available=is_available,
        test_drive_enabled=test_drive_enabled,
        search=search,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
    if page is not None and page_size is not None:
        total = vehicle_service.count_vehicles(
            db,
            dealership_id,
            include_archived_brands=include_archived_brands,
            brand_id=brand_id,
            min_price=min_price,
            max_price=max_price,
            status=status,
            is_available=is_available,
            test_drive_enabled=test_drive_enabled,
            search=search,
        )
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Page"] = str(page)
        response.headers["X-Page-Size"] = str(page_size)
        response.headers["X-Total-Pages"] = str(math.ceil(total / page_size) if page_size > 0 else 1)
    return vehicles


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.get_vehicle(db, dealership_id, vehicle_id, current_user)


@router.get(
    "/{vehicle_id}/images",
    response_model=list[VehicleImageResponse],
)
def list_vehicle_images(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VehicleImage]:
    return vehicle_image_service.list_images(
        db,
        dealership_id,
        vehicle_id,
        current_user,
    )


@router.post(
    "/{vehicle_id}/images",
    response_model=VehicleImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_vehicle_image(
    dealership_id: int,
    vehicle_id: int,
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None, max_length=255),
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> VehicleImage:
    content = file.file.read(vehicle_image_service.MAX_VEHICLE_IMAGE_SIZE + 1)
    return vehicle_image_service.upload_image(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        file.content_type,
        content,
        alt_text,
    )


@router.patch(
    "/{vehicle_id}/images/{image_id}",
    response_model=VehicleImageResponse,
)
def update_vehicle_image(
    dealership_id: int,
    vehicle_id: int,
    image_id: int,
    payload: VehicleImageUpdateRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> VehicleImage:
    return vehicle_image_service.update_image(
        db,
        dealership_id,
        vehicle_id,
        image_id,
        current_user,
        payload,
    )


@router.delete(
    "/{vehicle_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_vehicle_image(
    dealership_id: int,
    vehicle_id: int,
    image_id: int,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> None:
    vehicle_image_service.delete_image(
        db,
        dealership_id,
        vehicle_id,
        image_id,
        current_user,
    )


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


@router.patch("/{vehicle_id}/status", response_model=VehicleResponse)
def transition_vehicle_status(
    dealership_id: int,
    vehicle_id: int,
    payload: VehicleStatusTransitionRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.transition_vehicle_status(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        payload,
    )


@router.get("/{vehicle_id}/history", response_model=list[VehicleStatusHistoryResponse])
def get_vehicle_status_history(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VehicleStatusHistoryResponse]:
    history_records = vehicle_service.get_vehicle_status_history(
        db,
        dealership_id,
        vehicle_id,
        current_user,
    )
    return [
        VehicleStatusHistoryResponse(
            id=item.id,
            dealership_id=item.dealership_id,
            vehicle_id=item.vehicle_id,
            changed_by_user_id=item.changed_by_user_id,
            changed_by_user_email=item.changed_by_user.email if item.changed_by_user else None,
            previous_status=item.previous_status,
            new_status=item.new_status,
            notes=item.notes,
            created_at=item.created_at,
        )
        for item in history_records
    ]
