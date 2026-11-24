from typing import Any
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_role_access
from app.core.roles import STAFF_ROLES
from app.models.audit import AuditLog
from app.models.user import User
from app.repositories import audit_repository


def log_event(
    db: Session,
    action: str,
    resource_type: str,
    *,
    resource_id: str | None = None,
    dealership_id: int | None = None,
    actor: User | None = None,
    actor_email: str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    resolved_email = actor.email if actor else actor_email
    resolved_actor_id = actor.id if actor else None
    resolved_dealership_id = dealership_id or (actor.dealership_id if actor else None)

    audit_entry = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        dealership_id=resolved_dealership_id,
        actor_id=resolved_actor_id,
        actor_email=resolved_email,
        ip_address=ip_address,
        details=details,
    )
    return audit_repository.create_log(db, audit_entry)


def list_dealership_audit_logs(
    db: Session,
    dealership_id: int,
    current_user: User,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AuditLog], int]:
    ensure_dealership_role_access(current_user, dealership_id, *STAFF_ROLES)
    offset = max(0, (page - 1) * page_size)
    return audit_repository.list_logs(
        db,
        dealership_id=dealership_id,
        action=action,
        resource_type=resource_type,
        limit=page_size,
        offset=offset,
    )
