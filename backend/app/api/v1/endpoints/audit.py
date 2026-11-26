from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.services import audit_service

router = APIRouter(
    prefix="/dealerships/{dealership_id}/audit-logs",
    tags=["Audit Logs"],
)


@router.get(
    "",
    summary="List Dealership Audit Logs",
    description="Authorized dealership staff can inspect security, system, and agent activity trails.",
)
def list_audit_logs(
    dealership_id: int,
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items, total = audit_service.list_dealership_audit_logs(
        db,
        dealership_id,
        current_user,
        action=action,
        resource_type=resource_type,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [
            {
                "id": log.id,
                "dealership_id": log.dealership_id,
                "actor_id": log.actor_id,
                "actor_email": log.actor_email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
