from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.models.workspace import Brand
from app.schemas.workspace import BrandCreateRequest, BrandResponse, BrandUpdateRequest
from app.services import brand_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}/brands",
    tags=["Brands"],
)


@router.get("", response_model=list[BrandResponse])
def list_brands(
    dealership_id: int,
    include_inactive: bool = False,
    include_deleted: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Brand]:
    return brand_service.list_brands(
        db,
        dealership_id,
        current_user,
        include_inactive=include_inactive,
        include_deleted=include_deleted,
    )


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
def create_brand(
    dealership_id: int,
    payload: BrandCreateRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> Brand:
    return brand_service.create_brand(db, dealership_id, current_user, payload)


@router.post("/{brand_id}/restore", response_model=BrandResponse)
def restore_brand(
    dealership_id: int,
    brand_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> Brand:
    return brand_service.restore_brand(db, dealership_id, brand_id, current_user)


@router.put("/{brand_id}/logo", response_model=BrandResponse)
async def upload_brand_logo(
    dealership_id: int,
    brand_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> Brand:
    content = await file.read(brand_service.MAX_LOGO_SIZE + 1)
    return brand_service.upload_brand_logo(
        db,
        dealership_id,
        brand_id,
        current_user,
        file.content_type,
        content,
    )


@router.delete("/{brand_id}/logo", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand_logo(
    dealership_id: int,
    brand_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    brand_service.delete_brand_logo(db, dealership_id, brand_id, current_user)


@router.patch("/{brand_id}", response_model=BrandResponse)
def update_brand(
    dealership_id: int,
    brand_id: int,
    payload: BrandUpdateRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> Brand:
    return brand_service.update_brand(
        db,
        dealership_id,
        brand_id,
        current_user,
        payload,
    )


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(
    dealership_id: int,
    brand_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    brand_service.delete_brand(db, dealership_id, brand_id, current_user)


@router.get("/{brand_id}", response_model=BrandResponse)
def get_brand(
    dealership_id: int,
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Brand:
    return brand_service.get_brand(db, dealership_id, brand_id, current_user)
