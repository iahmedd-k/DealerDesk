import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import SQLAlchemyError
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
from app.core.roles import STAFF_ROLES
from app.core.supabase import get_supabase_client
from app.models.user import User
from app.models.workspace import Vehicle, VehicleImage
from app.repositories import vehicle_image_repository
from app.repositories import vehicle_repository
from app.schemas.workspace import VehicleImageUpdateRequest
from app.services import dealership_service


logger = logging.getLogger(__name__)
MAX_VEHICLE_IMAGE_SIZE = 10 * 1024 * 1024
MAX_IMAGES_PER_VEHICLE = 10
IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def list_images(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
) -> list[VehicleImage]:
    _get_vehicle(db, dealership_id, vehicle_id, current_user)
    return vehicle_image_repository.list_for_vehicle(db, dealership_id, vehicle_id)


def upload_image(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
    content_type: str | None,
    content: bytes,
    alt_text: str | None,
) -> VehicleImage:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    _get_vehicle(db, dealership_id, vehicle_id, current_user)
    if vehicle_image_repository.lock_vehicle(db, dealership_id, vehicle_id) is None:
        raise NotFoundError("Vehicle not found")
    content_type = (content_type or "").split(";", 1)[0].strip().lower()
    _validate_image(content_type, content)
    if alt_text is not None and len(alt_text) > 255:
        raise UnprocessableEntityError("Alt text must be 255 characters or fewer")

    existing_images = vehicle_image_repository.list_for_vehicle(
        db, dealership_id, vehicle_id
    )
    if len(existing_images) >= MAX_IMAGES_PER_VEHICLE:
        raise ConflictError(
            f"A vehicle can have at most {MAX_IMAGES_PER_VEHICLE} images"
        )

    object_path = (
        f"dealerships/{dealership_id}/vehicles/{vehicle_id}/"
        f"{uuid.uuid4().hex}.{IMAGE_EXTENSIONS[content_type]}"
    )
    bucket = get_settings().vehicle_images_bucket_id
    try:
        client = get_supabase_client()
    except RuntimeError as exc:
        raise ServiceUnavailableError(
            "Vehicle image storage is not configured"
        ) from exc

    try:
        storage = client.storage.from_(bucket)
        storage.upload(
            object_path,
            content,
            {
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "false",
            },
        )
        public_url = storage.get_public_url(object_path)
    except (StorageException, httpx.HTTPError) as exc:
        logger.error("Vehicle image upload failed for vehicle_id=%s", vehicle_id)
        raise BadGatewayError("Vehicle image upload failed") from exc

    image = VehicleImage(
        dealership_id=dealership_id,
        vehicle_id=vehicle_id,
        uploaded_by_user_id=current_user.id,
        storage_path=object_path,
        public_url=public_url,
        media_type=content_type,
        alt_text=alt_text,
        position=len(existing_images),
        created_at=datetime.now(timezone.utc),
    )
    try:
        return vehicle_image_repository.create(db, image)
    except SQLAlchemyError:
        db.rollback()
        try:
            client.storage.from_(bucket).remove([object_path])
        except (StorageException, httpx.HTTPError):
            logger.error(
                "Orphaned vehicle image cleanup failed for vehicle_id=%s",
                vehicle_id,
            )
        raise


def update_image(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    image_id: int,
    current_user: User,
    payload: VehicleImageUpdateRequest,
) -> VehicleImage:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    _get_vehicle(db, dealership_id, vehicle_id, current_user)
    if vehicle_image_repository.lock_vehicle(db, dealership_id, vehicle_id) is None:
        raise NotFoundError("Vehicle not found")
    images = vehicle_image_repository.list_for_vehicle(db, dealership_id, vehicle_id)
    image = next((item for item in images if item.id == image_id), None)
    if image is None:
        raise NotFoundError("Vehicle image not found")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise UnprocessableEntityError("At least one image field is required")
    if "position" in updates:
        position = updates["position"]
        if position is None:
            raise UnprocessableEntityError("Image position cannot be null")
        if position >= len(images):
            raise UnprocessableEntityError(
                "Image position must be within the vehicle image list"
            )
        images.remove(image)
        images.insert(position, image)
    if "alt_text" in updates:
        image.alt_text = updates["alt_text"]
    vehicle_image_repository.save_positions(db, images)
    return image


def delete_image(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    image_id: int,
    current_user: User,
) -> None:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    _get_vehicle(db, dealership_id, vehicle_id, current_user)
    if vehicle_image_repository.lock_vehicle(db, dealership_id, vehicle_id) is None:
        raise NotFoundError("Vehicle not found")
    images = vehicle_image_repository.list_for_vehicle(db, dealership_id, vehicle_id)
    image = next((item for item in images if item.id == image_id), None)
    if image is None:
        raise NotFoundError("Vehicle image not found")
    try:
        client = get_supabase_client()
    except RuntimeError as exc:
        raise ServiceUnavailableError(
            "Vehicle image storage is not configured"
        ) from exc
    try:
        client.storage.from_(get_settings().vehicle_images_bucket_id).remove(
            [image.storage_path]
        )
    except (StorageException, httpx.HTTPError) as exc:
        logger.error(
            "Vehicle image deletion failed for vehicle_id=%s image_id=%s",
            vehicle_id,
            image_id,
        )
        raise BadGatewayError("Vehicle image deletion failed") from exc
    images.remove(image)
    vehicle_image_repository.delete(db, image, images)


def _validate_image(content_type: str, content: bytes) -> None:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise UnsupportedMediaTypeError("Vehicle image must be JPEG, PNG, or WebP")
    if len(content) > MAX_VEHICLE_IMAGE_SIZE:
        raise PayloadTooLargeError("Vehicle image must be 10 MB or smaller")
    if not has_valid_image_signature(content_type, content):
        raise UnprocessableEntityError("Image content does not match its type")


def _get_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
    current_user: User,
) -> Vehicle:
    ensure_dealership_access(current_user, dealership_id)
    dealership_service.get_active_dealership(db, dealership_id)
    vehicle = vehicle_repository.get_for_dealership(db, dealership_id, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    return vehicle
