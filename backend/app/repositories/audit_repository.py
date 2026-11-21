from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def create_log(db: Session, log: AuditLog) -> AuditLog:
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_logs(
    db: Session,
    *,
    dealership_id: int | None = None,
    action: str | None = None,
    actor_id: int | None = None,
    resource_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    if dealership_id is not None:
        query = query.where(AuditLog.dealership_id == dealership_id)
    if action is not None:
        query = query.where(AuditLog.action == action)
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)
    if resource_type is not None:
        query = query.where(AuditLog.resource_type == resource_type)

    total = len(list(db.scalars(query)))
    items = list(
        db.scalars(
            query.order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total
