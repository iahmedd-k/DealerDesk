from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.authorization import ensure_dealership_access, ensure_role
from app.core.errors import ForbiddenError
from app.core.roles import DEALERDESK_ADMIN_ROLE
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories import dealership_repository


def require_dealerdesk_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != DEALERDESK_ADMIN_ROLE:
        raise ForbiddenError("DealerDesk admin access is required")
    return current_user


def require_roles(*roles: str) -> Callable[[User], User]:
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role == DEALERDESK_ADMIN_ROLE:
            return current_user
        ensure_role(current_user, *roles)
        if current_user.dealership_id is None:
            raise ForbiddenError("A dealership workspace is required")
        dealership = dealership_repository.get_by_id(
            db, current_user.dealership_id
        )
        if dealership is None or not dealership.is_active:
            raise ForbiddenError("The dealership workspace is inactive")
        return current_user

    return dependency


def require_dealership_roles(*roles: str) -> Callable[[User], User]:
    def dependency(
        dealership_id: int,
        current_user: User = Depends(require_roles(*roles)),
    ) -> User:
        ensure_dealership_access(current_user, dealership_id)
        return current_user

    return dependency
