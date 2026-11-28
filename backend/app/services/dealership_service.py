import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import (
    ensure_dealership_admin_access,
)
from app.core.errors import ConflictError, NotFoundError
from app.core.redis import redis_client
from app.models.user import User
from app.models.workspace import Dealership
from app.repositories import dealership_repository, user_repository
from app.schemas.workspace import (
    DealershipRegistrationRequest,
    DealershipSubscriptionUpdateRequest,
    DealershipUpdateRequest,
)
from app.services import auth_service, email_service

logger = logging.getLogger(__name__)


def list_active_dealerships(db: Session) -> list[Dealership]:
    return dealership_repository.list_active(db)


def list_detailed_dealerships(db: Session) -> list[dict]:
    return dealership_repository.list_detailed(db)


def get_platform_metrics(db: Session) -> dict:
    return dealership_repository.get_platform_metrics(db)


def get_active_dealership(db: Session, dealership_id: int) -> Dealership:
    dealership = dealership_repository.get_active_by_id(db, dealership_id)
    if dealership is None:
        raise NotFoundError("Dealership not found")
    return dealership


def update_subscription(
    db: Session,
    dealership_id: int,
    payload: DealershipSubscriptionUpdateRequest,
) -> Dealership:
    dealership = dealership_repository.get_by_id(db, dealership_id)
    if dealership is None:
        raise NotFoundError("Dealership not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(dealership, field, value)

    saved = dealership_repository.save(db, dealership)
    redis_client.delete("dealerdesk:public:dealerships")
    return saved


def register_dealership(db: Session, payload: DealershipRegistrationRequest) -> User:
    admin_email = str(payload.admin_email).lower()
    dealership_email = str(payload.dealership_email).lower()

    if user_repository.get_by_email(db, admin_email):
        raise ConflictError("Admin email is already registered")

    try:
        admin_user = dealership_repository.create_registration(
            db,
            name=payload.dealership_name,
            email=dealership_email,
            phone=payload.dealership_phone,
            address=payload.dealership_address,
            timezone=payload.timezone,
            brand_names=payload.brands,
            admin_name=payload.admin_name,
            admin_email=admin_email,
            admin_password=auth_service.hash_password(payload.admin_password),
        )
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Dealership registration conflicts with existing data"
        ) from exc

    try:
        email_service.send_dealership_welcome(
            recipient=admin_email,
            admin_name=payload.admin_name,
            dealership_name=payload.dealership_name,
            dealership_email=dealership_email,
            timezone_name=payload.timezone,
        )
    except Exception as exc:
        logger.warning("Dealership welcome email failed for %s: %s", admin_email, exc)
    return admin_user


def update_dealership(
    db: Session,
    dealership_id: int,
    current_user: User,
    payload: DealershipUpdateRequest,
) -> Dealership:
    ensure_dealership_admin_access(current_user, dealership_id)
    dealership = get_active_dealership(db, dealership_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None or field == "whatsapp_number":
            setattr(
                dealership,
                field,
                str(value).lower() if field == "email" else value,
            )

    saved = dealership_repository.save(db, dealership)
    redis_client.delete("dealerdesk:public:dealerships")
    return saved


def delete_dealership(db: Session, dealership_id: int, current_user: User) -> None:
    ensure_dealership_admin_access(current_user, dealership_id)
    dealership = get_active_dealership(db, dealership_id)
    dealership.is_active = False
    dealership_repository.commit(db)
