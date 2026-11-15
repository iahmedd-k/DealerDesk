from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User


def require_roles(*roles: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This role cannot perform the requested operation",
            )
        if current_user.dealership_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A dealership workspace is required",
            )
        return current_user

    return dependency
