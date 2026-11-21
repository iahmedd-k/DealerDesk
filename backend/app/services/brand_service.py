import logging

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from storage3.utils import StorageException

from app.core.authorization import (
    ensure_dealership_access,
    ensure_dealership_role_access,
)
from app.core.config import get_settings
from app.core.errors import (
    BadGatewayError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
)
from app.core.image_validation import ALLOWED_IMAGE_TYPES, has_valid_image_signature
from app.core.roles import DEALERSHIP_MANAGEMENT_ROLES
from app.core.supabase import get_supabase_client
from app.models.user import User
from app.models.workspace import Brand
from app.repositories import brand_repository
from app.schemas.workspace import BrandCreateRequest, BrandUpdateRequest
from app.services import dealership_service


logger = logging.getLogger(__name__)
MAX_LOGO_SIZE = 3 * 1024 * 1024
MAX_BRANDS_PER_DEALERSHIP = 20


def list_brands(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    include_inactive: bool = False,
    include_deleted: bool = False,
) -> list[Brand]:
    if include_inactive or include_deleted:
        ensure_dealership_role_access(
            current_user,
            dealership_id,
            *DEALERSHIP_MANAGEMENT_ROLES,
        )
    else:
        ensure_dealership_access(current_user, dealership_id)
    dealership_service.get_active_dealership(db, dealership_id)
    return brand_repository.list_for_dealership(
        db,
        dealership_id,
        include_inactive=include_inactive,
        include_deleted=include_deleted,
    )


def create_brand(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: BrandCreateRequest,
) -> Brand:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    if brand_repository.lock_active_dealership(db, dealership_id) is None:
        raise NotFoundError("Dealership not found")
    if (
        brand_repository.count_not_deleted(db, dealership_id)
        >= MAX_BRANDS_PER_DEALERSHIP
    ):
        raise ConflictError("A dealership can have at most 20 brands")
    try:
        return brand_repository.create(
            db,
            Brand(dealership_id=dealership_id, name=payload.name),
        )
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("This dealership already has that brand") from exc


def restore_brand(
    db: Session,
    dealership_id: int,
    brand_id: int,
    current_user: User,
) -> Brand:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    if brand_repository.lock_active_dealership(db, dealership_id) is None:
        raise NotFoundError("Dealership not found")
    brand = _get_brand(db, dealership_id, brand_id, include_deleted=True)
    if not brand.is_deleted:
        raise ConflictError("Brand is not deleted")
    if (
        brand_repository.count_not_deleted(db, dealership_id)
        >= MAX_BRANDS_PER_DEALERSHIP
    ):
        raise ConflictError("A dealership can have at most 20 brands")
    brand.is_deleted = False
    brand.is_active = False
    try:
        return brand_repository.save(db, brand)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A brand with this name already exists") from exc


def upload_brand_logo(
    db: Session,
    dealership_id: int,
    brand_id: int,
    current_user: User,
    content_type: str | None,
    content: bytes,
) -> Brand:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    dealership_service.get_active_dealership(db, dealership_id)
    brand = _get_brand(db, dealership_id, brand_id)
    content_type = content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise UnsupportedMediaTypeError("Logo must be a JPEG, PNG, or WebP image")
    if len(content) > MAX_LOGO_SIZE:
        raise PayloadTooLargeError("Logo must be 3 MB or smaller")
    if not has_valid_image_signature(content_type, content):
        raise UnprocessableEntityError("Logo content does not match its type")
    try:
        client = get_supabase_client()
    except RuntimeError as exc:
        raise ServiceUnavailableError("Brand logo storage is not configured") from exc
    logo_path = f"dealerships/{dealership_id}/brands/{brand_id}/logo"
    bucket = get_settings().supabase_bucket_id
    try:
        client.storage.from_(bucket).upload(
            logo_path,
            content,
            {
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "true",
            },
        )
        brand.logo_url = client.storage.from_(bucket).get_public_url(logo_path)
    except (StorageException, httpx.HTTPError) as exc:
        logger.error("Brand logo upload failed for brand_id=%s", brand_id)
        raise BadGatewayError("Brand logo upload failed") from exc
    brand.logo_path = logo_path
    return brand_repository.save(db, brand)


def delete_brand_logo(
    db: Session,
    dealership_id: int,
    brand_id: int,
    current_user: User,
) -> None:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    dealership_service.get_active_dealership(db, dealership_id)
    brand = _get_brand(db, dealership_id, brand_id)
    if brand.logo_path is None:
        return
    try:
        get_supabase_client().storage.from_(get_settings().supabase_bucket_id).remove(
            [brand.logo_path]
        )
    except (RuntimeError, StorageException, httpx.HTTPError) as exc:
        logger.error("Brand logo deletion failed for brand_id=%s", brand_id)
        raise BadGatewayError("Brand logo deletion failed") from exc
    brand.logo_path = None
    brand.logo_url = None
    brand_repository.save(db, brand)


def update_brand(
    db: Session,
    dealership_id: int,
    brand_id: int,
    current_user: User,
    payload: BrandUpdateRequest,
) -> Brand:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    dealership_service.get_active_dealership(db, dealership_id)
    brand = _get_brand(db, dealership_id, brand_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise UnprocessableEntityError("At least one field is required")
    if updates.get("is_active") is False and brand.is_active:
        brand_repository.deactivate_future_slots(db, brand.id)
    renamed = updates.get("name") is not None
    if renamed:
        brand.name = updates["name"]
    for field, value in updates.items():
        if field != "name" and value is not None:
            setattr(brand, field, value)
    try:
        return brand_repository.save(db, brand, update_vehicle_make=renamed)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A brand with this name already exists") from exc


def delete_brand(
    db: Session,
    dealership_id: int,
    brand_id: int,
    current_user: User,
) -> None:
    ensure_dealership_role_access(
        current_user,
        dealership_id,
        *DEALERSHIP_MANAGEMENT_ROLES,
    )
    dealership_service.get_active_dealership(db, dealership_id)
    brand = _get_brand(db, dealership_id, brand_id)
    brand_repository.deactivate_future_slots(db, brand.id)
    brand.is_active = False
    brand.is_deleted = True
    brand_repository.save(db, brand)


def get_brand(
    db: Session,
    dealership_id: int,
    brand_id: int,
    current_user: User,
) -> Brand:
    ensure_dealership_access(current_user, dealership_id)
    dealership_service.get_active_dealership(db, dealership_id)
    return _get_brand(db, dealership_id, brand_id)


def _get_brand(
    db: Session,
    dealership_id: int,
    brand_id: int,
    *,
    include_deleted: bool = False,
) -> Brand:
    brand = brand_repository.get_for_dealership(
        db,
        dealership_id,
        brand_id,
        include_deleted=include_deleted,
    )
    if brand is None:
        raise NotFoundError("Brand not found")
    return brand
