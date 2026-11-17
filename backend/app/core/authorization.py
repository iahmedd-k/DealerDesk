from app.core.errors import ForbiddenError, NotFoundError
from app.core.roles import DEALERSHIP_ADMIN_ROLE
from app.models.user import User


def ensure_role(current_user: User, *roles: str) -> None:
    if current_user.role not in roles:
        raise ForbiddenError("This role cannot perform the requested operation")


def ensure_dealership_access(current_user: User, dealership_id: int) -> None:
    if current_user.dealership_id != dealership_id:
        raise NotFoundError("Dealership not found")


def ensure_dealership_admin(current_user: User) -> None:
    ensure_role(current_user, DEALERSHIP_ADMIN_ROLE)


def ensure_dealership_admin_access(
    current_user: User,
    dealership_id: int,
) -> None:
    if (
        current_user.dealership_id != dealership_id
        or current_user.role != DEALERSHIP_ADMIN_ROLE
    ):
        raise ForbiddenError("Dealership admin access is required")
